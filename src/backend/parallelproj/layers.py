"""PyTorch autograd layers wrapping parallelproj linear operators.

These are adapted from the parallelproj documentation (see
``docs/superpowers/code/parallelproj_operators.py``) but reference the
v2.x path ``parallelproj.operators.LinearOperator``.

``LinearSingleChannelOperator`` maps a mini-batch of single-channel 3-D images
``(B, 1, nx, ny, nz)`` to a batch of projection tensors
``(B, *operator.out_shape)`` and its backward pass performs the adjoint. It is
the forward-projection layer. ``AdjointLinearSingleChannelOperator`` is the
mirror layer (back projection). ``ReshapeLayer`` is a small reshape helper that
re-exposes the forward/backward axis book-keeping of the docs example.
"""

from typing import Optional, Sequence, Tuple

import torch

try:  # pragma: no cover - import availability guards
    from parallelproj.operators import LinearOperator
except ImportError:  # pragma: no cover
    LinearOperator = object  # type: ignore[assignment,misc]


def _device_of(data: torch.Tensor):
    """Return the PyTorch device of ``data`` (array-api ``device`` shim)."""
    return data.device


class LinearSingleChannelOperator(torch.autograd.Function):
    """Forward-projection operator: maps a volume batch to a projection batch.

    Maps a mini batch of single-channel 3-D images
    ``(batch_size, 1, nx, ny, nz)`` to a mini batch of projection tensors of
    shape ``(batch_size, *operator.out_shape)`` by applying the parallelproj
    linear operator to each volume in the batch. The backward pass applies the
    operator's adjoint.
    """

    @staticmethod
    def forward(ctx, img: torch.Tensor, operator) -> torch.Tensor:
        """Apply the forward projection operator.

        Args:
            img: mini batch of 3-D images, shape ``(B, 1, nx, ny, nz)``.
            operator: a parallelproj :class:`LinearOperator`.

        Returns:
            Mini batch of projections, shape ``(B, *operator.out_shape)``.
        """
        ctx.set_materialize_grads(False)
        ctx.operator = operator

        batch_size = img.shape[0]
        proj = torch.zeros(
            (batch_size,) + operator.out_shape, dtype=img.dtype, device=_device_of(img)
        )

        for i in range(batch_size):
            proj[i, ...] = operator(img[i, 0, ...].detach())

        return proj

    @staticmethod
    def backward(ctx, grad_output):
        """Backward pass of the forward projection (adjoint back projection)."""
        if grad_output is None:
            return None, None

        operator = ctx.operator
        batch_size = grad_output.shape[0]
        x = torch.zeros(
            (batch_size, 1) + operator.in_shape,
            dtype=grad_output.dtype,
            device=_device_of(grad_output),
        )

        for i in range(batch_size):
            x[i, 0, ...] = operator.adjoint(grad_output[i, ...].detach())

        return x, None


class AdjointLinearSingleChannelOperator(torch.autograd.Function):
    """Back-projection operator: maps a projection batch to a volume batch.

    Maps a mini batch of projections ``(B, 1, *operator.out_shape)`` to a mini
    batch of single-channel 3-D images ``(B, 1, *operator.in_shape)`` via the
    operator's adjoint. The backward pass applies the operator itself.
    """

    @staticmethod
    def forward(ctx, proj: torch.Tensor, operator) -> torch.Tensor:
        """Apply the adjoint (back projection) operator.

        Args:
            proj: mini batch of projections, shape ``(B, 1, *operator.out_shape)``.
            operator: a parallelproj :class:`LinearOperator`.

        Returns:
            Mini batch of 3-D images, shape ``(B, 1, *operator.in_shape)``.
        """
        ctx.set_materialize_grads(False)
        ctx.operator = operator

        batch_size = proj.shape[0]
        img = torch.zeros(
            (batch_size, 1) + operator.in_shape,
            dtype=proj.dtype,
            device=_device_of(proj),
        )

        for i in range(batch_size):
            img[i, 0, ...] = operator.adjoint(proj[i, ...].detach())

        return img

    @staticmethod
    def backward(ctx, grad_output):
        """Backward pass of the adjoint (forward projection)."""
        if grad_output is None:
            return None, None

        operator = ctx.operator
        batch_size = grad_output.shape[0]
        x = torch.zeros(
            (batch_size,) + operator.out_shape,
            dtype=grad_output.dtype,
            device=_device_of(grad_output),
        )

        for i in range(batch_size):
            x[i, ...] = operator(grad_output[i, 0, ...].detach())

        return x, None


class ReshapeLayer(torch.nn.Module):
    """Reshape layer with optional axis swaps/moves before/after reshaping."""

    def __init__(
        self,
        new_shape: Sequence[int],
        swap_axis_before: Optional[Tuple[int, int]] = None,
        swap_axis_after: Optional[Tuple[int, int]] = None,
        move_axis_before: Optional[Tuple[int, int]] = None,
    ):
        """Initialize the reshape layer.

        Args:
            new_shape: Target shape (batch size is prepended by :meth:`forward`).
            swap_axis_before: Indices of two axes swapped before reshaping.
            swap_axis_after: Indices of two axes swapped after reshaping.
            move_axis_before: ``(source, dest)`` axes to move before reshaping.
        """
        super().__init__()
        self.new_shape = new_shape
        self.old_shape: Optional[Tuple[int, ...]] = None
        self.swap_axis_before = swap_axis_before
        self.swap_axis_after = swap_axis_after
        self.move_axis_before = move_axis_before

    def forward(self, data: torch.Tensor, batch_size: int) -> torch.Tensor:
        """Reshape ``data`` into ``(batch_size, *new_shape)``."""
        self.old_shape = tuple(data.shape)

        if self.swap_axis_before is not None:
            data = torch.swapaxes(
                data, self.swap_axis_before[0], self.swap_axis_before[1]
            )

        if self.move_axis_before is not None:
            data = torch.moveaxis(
                data, self.move_axis_before[0], self.move_axis_before[1]
            )

        new_shape = [batch_size]
        new_shape.extend(self.new_shape)
        data = torch.reshape(data, shape=new_shape)

        if self.swap_axis_after is not None:
            data = torch.swapaxes(
                data, self.swap_axis_after[0], self.swap_axis_after[1]
            )

        return data

    def backward(self, grad: torch.Tensor) -> torch.Tensor:
        """Inverse of :meth:`forward` (for completeness)."""
        if self.swap_axis_after is not None:
            grad = torch.swapaxes(
                grad, self.swap_axis_after[1], self.swap_axis_after[0]
            )

        if self.old_shape is not None:
            grad = torch.reshape(grad, shape=self.old_shape)

        if self.swap_axis_before is not None:
            grad = torch.swapaxes(
                grad, self.swap_axis_before[1], self.swap_axis_before[0]
            )

        return grad
