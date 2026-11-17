# Running CTBeamStudio from the Docker image

This is the operator-facing guide for running CTBeamStudio as a container. It
assumes no Python, no conda, and no network access after the image is on the
machine. Everything the app needs is inside the image.

The image to use is **`ctbeamstudio:1.0.0`** — version tags always mean the
`full` variant, the one with forward projection. `slim` is a local build
target only and is never published (see [Troubleshooting](#troubleshooting)).

## 1. What you need

| | Requirement |
|---|---|
| Docker | Docker Desktop (Windows 10/11, macOS) or Docker Engine (Linux) |
| RAM | 8 GB minimum, 16 GB+ for large CT series |
| Free disk | ~4 GB for the image, plus space for your DICOM data |
| GPU | not required — the image ships the CPU build of parallelproj |

No internet connection is needed after the image has been loaded once.

## 2. Get the image onto the machine

**From a tarball** (works offline, no registry account):

```bash
docker load -i ctbeamstudio-1.0.0-full.tar
```

**From the registry** (once the publish job exists, see `docs/plan.md` T-105):

```bash
docker pull ghcr.io/lhell/ctbeamstudio:1.0.0
```

Confirm it arrived:

```bash
docker images ctbeamstudio
```

## 3. Start the container

The app reads DICOM series from a **folder path inside the container**, so the
folder has to be mounted. `:ro` keeps the container from ever writing to your
data:

**Windows (PowerShell)**

```powershell
docker run -d --name ctbeamstudio -p 8501:8501 `
  -v "C:\data\ct:/data:ro" `
  -v ctbeamstudio-cache:/app/data `
  --restart unless-stopped `
  ctbeamstudio:1.0.0
```

**Linux / macOS**

```bash
docker run -d --name ctbeamstudio -p 8501:8501 \
  -v /data/ct:/data:ro \
  -v ctbeamstudio-cache:/app/data \
  --restart unless-stopped \
  ctbeamstudio:1.0.0
```

| Flag | Why |
|---|---|
| `-p 8501:8501` | the web UI on http://localhost:8501 |
| `-v <host>:/data:ro` | your DICOM data, read-only |
| `-v ctbeamstudio-cache:/app/data` | keeps the app's own cache across container restarts |
| `--restart unless-stopped` | comes back after a reboot |
| `-d` | runs in the background |

On Docker Desktop the mounted host folder must be shared with Docker
(Settings → Resources → File sharing). Add more mounts if you keep data in
several places.

## 4. Use it

1. Open **http://localhost:8501**.
2. In the sidebar under **Image → DICOM Folder**, type the container path of
   your series, e.g. `/data/study_042/series_3`.
3. Pick the series from **Select Series**, adjust slices, and work as usual.

Restarting the browser does not stop the container; `localhost:8501` keeps
working as long as the container runs. Nothing is exposed to the network beyond
this machine unless you publish the port on a network interface.

## 5. Stop, update, remove

```bash
docker stop ctbeamstudio          # stop (data untouched)
docker start ctbeamstudio         # start again
docker logs ctbeamstudio          # see what the app printed
docker rm -f ctbeamstudio         # remove the container
docker load -i ctbeamstudio-1.0.1-full.tar && \
  docker rm -f ctbeamstudio &&  # then run the docker run command from step 3
```

To ship the image to another machine, export it there (versioned with the
release number):

```bash
docker save ctbeamstudio:1.0.0 -o ctbeamstudio-1.0.0-full.tar
```

## Troubleshooting

| Symptom | Cause / fix |
|---|---|
| `parallelproj not available. Forward projection will return zeros.` | You are not on the `full` variant. Use the version-tagged image (`ctbeamstudio:1.0.0`); `slim` is a local build target only. |
| `Ports are not available: 8501` | Something else uses 8501. Map another port: `-p 8502:8501`, then open port 8502. |
| The DICOM folder path shows no series | Path must be the **container** path (`/data/...`), not `C:\...`. Check the mount with `docker exec ctbeamstudio ls /data`. |
| `No DICOM files found` | Point at the folder that holds the `.dcm`/`.ima` files directly; the scanner does not descend into subfolders. |
| Browser cannot connect | Container not running (`docker ps`) or still starting (~10 s). `docker logs ctbeamstudio` shows the reason. |
| Permission denied writing `/app/data` | A host folder was mounted there instead of the named volume. Use `-v ctbeamstudio-cache:/app/data`. |

## Your data stays local

The container reads the mounted folder and writes nothing to it (`:ro`). The
only state it keeps is its own cache volume (`ctbeamstudio-cache`). No upload, no
telemetry, no connection to the developers — patient data never leaves the
machine you run it on.
