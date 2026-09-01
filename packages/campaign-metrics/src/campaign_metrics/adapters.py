"""Channel metrics adapters: connector pages -> neutral ProviderPage.

The adapters are structurally typed so this package never imports the
connector packages; the connectors' own ``fetch_metrics_page`` /
``fetch_gaql_page`` functions are injected by the caller. Real DEV/SIT
pulls run only in protected jobs — in this repo the connectors serve
deterministic mock fixtures.
"""

from __future__ import annotations

from typing import Any, Mapping, Protocol

from campaign_metrics.ingest import PageFetcher, ProviderPage, ProviderRow


class _ProviderMetricRow(Protocol):
    @property
    def provider_field_name(self) -> str: ...

    @property
    def provider_value(self) -> object: ...

    @property
    def provider_value_type(self) -> str: ...

    @property
    def source_response_hash(self) -> str: ...

    @property
    def retrieved_at(self) -> str: ...


class _LinkedInPage(Protocol):
    @property
    def rows(self) -> tuple[_ProviderMetricRow, ...]: ...

    @property
    def next_cursor(self) -> str | None: ...


class _GaqlPage(Protocol):
    @property
    def rows(self) -> tuple[_ProviderMetricRow, ...]: ...

    @property
    def next_page_token(self) -> str | None: ...


class _LinkedInFetch(Protocol):
    def __call__(
        self,
        *,
        config: Any,
        account_id: str,
        external_object_id: str,
        window: Mapping[str, str],
        cursor: str | None,
        retrieved_at: str,
    ) -> _LinkedInPage: ...


class _GaqlFetch(Protocol):
    def __call__(
        self,
        *,
        config: Any,
        customer_id_ref: str,
        external_object_id: str,
        window: Mapping[str, str],
        page_token: str | None,
        retrieved_at: str,
    ) -> _GaqlPage: ...


def _to_provider_page(
    rows: tuple[_ProviderMetricRow, ...],
    next_cursor: str | None,
    retrieved_at: str,
) -> ProviderPage:
    source_hash = rows[0].source_response_hash if rows else "sha256:" + "0" * 64
    return ProviderPage(
        rows=tuple(
            ProviderRow(
                field_name=row.provider_field_name,
                value=row.provider_value,
                value_type=row.provider_value_type,
            )
            for row in rows
        ),
        next_cursor=next_cursor,
        source_response_hash=source_hash,
        retrieved_at=retrieved_at,
    )


class _LinkedInFetcher:
    def __init__(
        self,
        *,
        config: Any,
        account_id: str,
        external_object_id: str,
        window: Mapping[str, str],
        retrieved_at: str,
        fetch_page: _LinkedInFetch,
    ) -> None:
        self._config = config
        self._account_id = account_id
        self._external_object_id = external_object_id
        self._window = dict(window)
        self._retrieved_at = retrieved_at
        self._fetch_page = fetch_page

    def fetch(self, cursor: str | None) -> ProviderPage:
        page = self._fetch_page(
            config=self._config,
            account_id=self._account_id,
            external_object_id=self._external_object_id,
            window=self._window,
            cursor=cursor,
            retrieved_at=self._retrieved_at,
        )
        return _to_provider_page(page.rows, page.next_cursor, self._retrieved_at)


class _GoogleAdsFetcher:
    def __init__(
        self,
        *,
        config: Any,
        customer_id_ref: str,
        external_object_id: str,
        window: Mapping[str, str],
        retrieved_at: str,
        fetch_page: _GaqlFetch,
    ) -> None:
        self._config = config
        self._customer_id_ref = customer_id_ref
        self._external_object_id = external_object_id
        self._window = dict(window)
        self._retrieved_at = retrieved_at
        self._fetch_page = fetch_page

    def fetch(self, cursor: str | None) -> ProviderPage:
        page = self._fetch_page(
            config=self._config,
            customer_id_ref=self._customer_id_ref,
            external_object_id=self._external_object_id,
            window=self._window,
            page_token=cursor,
            retrieved_at=self._retrieved_at,
        )
        return _to_provider_page(page.rows, page.next_page_token, self._retrieved_at)


def linkedin_fetcher(
    *,
    config: Any,
    account_id: str,
    external_object_id: str,
    window: Mapping[str, str],
    retrieved_at: str,
    fetch_page: _LinkedInFetch,
) -> PageFetcher:
    return _LinkedInFetcher(
        config=config,
        account_id=account_id,
        external_object_id=external_object_id,
        window=window,
        retrieved_at=retrieved_at,
        fetch_page=fetch_page,
    )


def google_ads_fetcher(
    *,
    config: Any,
    customer_id_ref: str,
    external_object_id: str,
    window: Mapping[str, str],
    retrieved_at: str,
    fetch_page: _GaqlFetch,
) -> PageFetcher:
    return _GoogleAdsFetcher(
        config=config,
        customer_id_ref=customer_id_ref,
        external_object_id=external_object_id,
        window=window,
        retrieved_at=retrieved_at,
        fetch_page=fetch_page,
    )
