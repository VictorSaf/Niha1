# Document Library — static files

This directory is mounted into the backend container at `/app/documents` (see `docker-compose.yml`).

Place here the **static** document files used by the Document Library (e.g. `NIHA_*.pdf`). Filenames must match the catalog in `backend/app/api/v1/documents.py` (`DOCUMENT_CATALOG`). Documents that are generated as PDFs by the backend (e.g. NDA, KYC, MSA) do not need to be in this folder.

Without these files, download requests for static documents will return 404 (Document file not found on server).

When adding or renaming entries in `DOCUMENT_CATALOG`, update this README if the naming convention or placement rules change.
