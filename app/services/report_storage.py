from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Protocol
from uuid import uuid4

from typing import TYPE_CHECKING

from app.core.config import get_settings

if TYPE_CHECKING:  # pragma: no cover
    from azure.storage.blob import BlobSasPermissions, BlobServiceClient


class StorageUploader(Protocol):
    def upload(self, *, customer_id: str, data: bytes) -> "UploadResult":
        ...


@dataclass(frozen=True)
class UploadResult:
    blob_path: str
    run_id: str
    url: str
    generated_at: datetime


class AzureBlobReportStorage(StorageUploader):
    def __init__(self) -> None:
        from azure.storage.blob import BlobSasPermissions, BlobServiceClient, generate_blob_sas  # type: ignore

        settings = get_settings()
        if not settings.azure_storage_account_url or not settings.azure_storage_account_key:
            raise RuntimeError("Azure storage account configuration missing")
        if not settings.azure_storage_container:
            raise RuntimeError("Azure storage container not configured")

        self._account_url = settings.azure_storage_account_url.rstrip("/")
        self._account_key = settings.azure_storage_account_key
        self._container = settings.azure_storage_container
        self._BlobSasPermissions: type[BlobSasPermissions] = BlobSasPermissions  # type: ignore[name-defined]
        self._generate_blob_sas = generate_blob_sas
        self._service_client: BlobServiceClient = BlobServiceClient(  # type: ignore[name-defined]
            account_url=self._account_url,
            credential=self._account_key,
        )
        self._account_name = self._service_client.account_name

    def upload(self, *, customer_id: str, data: bytes) -> UploadResult:
        now = datetime.utcnow()
        run_id = f"rpt_{uuid4().hex[:8]}"
        blob_path = self._build_blob_path(now=now, customer_id=customer_id, run_id=run_id)

        blob_client = self._service_client.get_blob_client(
            container=self._container,
            blob=blob_path,
        )
        blob_client.upload_blob(data, overwrite=True, content_type="application/pdf")

        sas_token = self._generate_blob_sas(
            account_name=self._account_name,
            container_name=self._container,
            blob_name=blob_path,
            account_key=self._account_key,
            permission=self._BlobSasPermissions(read=True),
            expiry=now + timedelta(days=1),
        )
        url = f"{self._account_url}/{self._container}/{blob_path}?{sas_token}"
        return UploadResult(blob_path=blob_path, run_id=run_id, url=url, generated_at=now)

    @staticmethod
    def _build_blob_path(*, now: datetime, customer_id: str, run_id: str) -> str:
        project = "fin-restructure"
        path = Path(
            project,
            f"yyyy={now:%Y}",
            f"mm={now:%m}",
            f"dd={now:%d}",
            f"customer_id={customer_id}",
            f"run={run_id}",
        ) / "report.pdf"
        return str(path).replace("\\", "/")
