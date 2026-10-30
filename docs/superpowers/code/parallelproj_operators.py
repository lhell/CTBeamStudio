"""Parallelproj operators for forward and back projection.

This code is adapted from parallelproj documentation:
https://parallelproj.readthedocs.io/en/stable/auto_examples/07_torch/01_run_projection_layer.html
"""

import parallelproj
import torch
from array_api_compat import device


class ReshapeLayer(torch.nn.Module):
    def __init__(
        self,
        new_shape,
        swap_axis_before=None,
        swap_axis_after=None,
        move_axis_before=None,
    ):
        """Reshape layer for tensor manipulation.

        Args:
            new_shape: Target shape for reshaping
            swap_axis_before: list, gives indices of two axes that are swapped before reshaping
            swap_axis_after: list, gives indices two axes that are swapped after reshaping
            move_axis_before: list, gives axis to move before reshaping
        """
        super(ReshapeLayer, self).__init__()
        self.new_shape = new_shape
        self.old_shape = None
        self.swap_axis_before = swap_axis_before
        self.swap_axis_after = swap_axis_after
        self.move_axis_before = move_axis_before

    def forward(self, data, batch_size):
        """Forward pass of reshape layer.

        Args:
            data: tensor to be reshaped
            batch_size: current data processing batch size

        Returns:
            Reshaped tensor
        """
        self.old_shape = data.shape  # store previous shape in class attribute

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

    def backward(self, grad):
        """Backward pass of reshape layer."""
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


class LinearSingleChannelOperator(torch.autograd.Function):
    """
    Function representing a linear operator acting on a mini batch of single channel images.

    This is the forward projection operator - maps 3D volume to 2D projections.
    """

    @staticmethod
    def forward(
        ctx, img: torch.Tensor, operator: parallelproj.LinearOperator
    ) -> torch.Tensor:
        """Forward pass of the linear operator.

        Parameters
        ----------
        ctx : context object
            that can be used to store information for the backward pass
        img : torch.Tensor
            mini batch of 3D images with dimension (batch_size, 1, num_voxels_x, num_voxels_y, num_voxels_z)
        operator : parallelproj.LinearOperator
            linear operator that can act on a single 3D image

        Returns
        -------
        torch.Tensor
            mini batch of 3D images with dimension (batch_size, operator.out_shape)
        """
        # https://pytorch.org/docs/stable/notes/extending.html#how-to-use
        ctx.set_materialize_grads(False)
        ctx.operator = operator

        batch_size = img.shape[0]
        proj = torch.zeros(
            (batch_size,) + operator.out_shape, dtype=img.dtype, device=device(img)
        )

        # loop over all samples in the batch and apply linear operator
        # to the first channel
        for i in range(batch_size):
            proj[i, ...] = operator(img[i, 0, ...].detach())

        return proj

    @staticmethod
    def backward(ctx, grad_output):
        """Backward pass of the forward pass.

        Parameters
        ----------
        ctx : context object
            that can be used to obtain information from the forward pass
        grad_output : torch.Tensor
            mini batch of dimension (batch_size, operator.out_shape)

        Returns
        -------
        torch.Tensor, None
            mini batch of 3D images with dimension (batch_size, 1, operator.in_shape)
        """
        # For details on how to implement the backward pass, see
        # https://pytorch.org/docs/stable/notes/extending.html#how-to-use

        # since forward takes two input arguments (x, operator)
        # we have to return two arguments (the latter is None)

        if grad_output is None:
            return None, None
        else:
            operator = ctx.operator

            batch_size = grad_output.shape[0]
            x = torch.zeros(
                (batch_size, 1) + operator.in_shape,
                dtype=grad_output.dtype,
                device=device(grad_output),
            )

            # loop over all samples in the batch and apply linear operator
            # to the first channel
            for i in range(batch_size):
                x[i, 0, ...] = operator.adjoint(grad_output[i, ...].detach())

            return x, None


class AdjointLinearSingleChannelOperator(torch.autograd.Function):
    """
    Function representing the adjoint of a linear operator acting on a mini batch of single channel images.

    This is the back projection operator - maps 2D projections back to 3D volume.
    """

    @staticmethod
    def forward(
        ctx, proj: torch.Tensor, operator: parallelproj.LinearOperator
    ) -> torch.Tensor:
        """Forward pass of the adjoint of the linear operator.

        Parameters
        ----------
        ctx : context object
            that can be used to store information for the backward pass
        proj : torch.Tensor
            mini batch of 3D images with dimension (batch_size, 1, operator.out_shape)
        operator : parallelproj.LinearOperator
            linear operator that can act on a single 3D image

        Returns
        -------
        torch.Tensor
            mini batch of 3D images with dimension (batch_size, 1, operator.in_shape)
        """
        ctx.set_materialize_grads(False)
        ctx.operator = operator

        batch_size = proj.shape[0]
        img = torch.zeros(
            (batch_size, 1) + operator.in_shape, dtype=proj.dtype, device=device(proj)
        )

        # loop over all samples in the batch and apply linear operator
        # to the first channel
        for i in range(batch_size):
            img[i, 0, ...] = operator.adjoint(proj[i, ...].detach())

        return img

    @staticmethod
    def backward(ctx, grad_output):
        """Backward pass of the forward pass.

        Parameters
        ----------
        ctx : context object
            that can be used to obtain information from the forward pass
        grad_output : torch.Tensor
            mini batch of dimension (batch_size, 1, operator.in_shape)

        Returns
        -------
        torch.Tensor, None
            mini batch of 3D images with dimension (batch_size, 1, operator.out_shape)
        """
        # For details on how to implement the backward pass, see
        # https://pytorch.org/docs/stable/notes/extending.html#how-to-use

        # since forward takes two input arguments (x, operator)
        # we have to return two arguments (the latter is None)
        if grad_output is None:
            return None, None
        else:
            operator = ctx.operator

            batch_size = grad_output.shape[0]
            x = torch.zeros(
                (batch_size,) + operator.out_shape,
                dtype=grad_output.dtype,
                device=device(grad_output),
            )

            # loop over all samples in the batch and apply linear operator
            # to the first channel
            for i in range(batch_size):
                x[i, ...] = operator(grad_output[i, 0, ...].detach())

            return x, None


# Wrapper functions for easy usage
def forward_project_torch(
    volume: torch.Tensor, operator: parallelproj.LinearOperator
) -> torch.Tensor:
    """Project a 3D volume to projections using parallelproj operator.

    Args:
        volume: 3D volume tensor of shape (batch_size, 1, nx, ny, nz)
        operator: parallelproj LinearOperator

    Returns:
        Projections tensor of shape (batch_size, *operator.out_shape)
    """
    return LinearSingleChannelOperator.apply(volume, operator)


def back_project_torch(
    projections: torch.Tensor, operator: parallelproj.LinearOperator
) -> torch.Tensor:
    """Back-project projections to 3D volume using parallelproj operator.

    Args:
        projections: Projections tensor of shape (batch_size, 1, *operator.out_shape)
        operator: parallelproj LinearOperator

    Returns:
        3D volume tensor of shape (batch_size, 1, *operator.in_shape)
    """
    return AdjointLinearSingleChannelOperator.apply(projections, operator)
