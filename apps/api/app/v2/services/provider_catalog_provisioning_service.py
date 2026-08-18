from __future__ import annotations

from dataclasses import dataclass

from app.v2.domain.provider_routing import (
    ProviderModelTarget,
)
from app.v2.repositories.provider_catalog import (
    ProviderCatalogRepository,
)


class ProviderCatalogProvisioningError(RuntimeError):
    pass


class ProviderCatalogDeclarationError(
    ProviderCatalogProvisioningError,
):
    pass


class ProviderCatalogDriftError(
    ProviderCatalogProvisioningError,
):
    pass


@dataclass(
    frozen=True,
    slots=True,
)
class ProviderCatalogProvisioningResult:
    targets: tuple[ProviderModelTarget, ...]
    created_target_ids: tuple[str, ...]


class ProviderCatalogProvisioningService:
    def __init__(
        self,
        *,
        catalog: ProviderCatalogRepository,
    ) -> None:
        self._catalog = catalog

    def provision(
        self,
        *,
        targets: tuple[ProviderModelTarget, ...],
    ) -> ProviderCatalogProvisioningResult:
        self._require_declarations(targets)

        try:
            existing_targets = self._catalog.list_targets(
                enabled_only=False,
                limit=10_000,
            )
        except Exception as exc:
            raise ProviderCatalogProvisioningError(
                "provider catalog provisioning listing failed"
            ) from exc

        existing_by_id = {
            target.target_id: target
            for target in existing_targets
        }
        existing_by_provider_model = {
            (
                target.provider.provider_id,
                target.model.model_id,
            ): target
            for target in existing_targets
        }

        for target in targets:
            existing = existing_by_id.get(
                target.target_id
            )

            if existing is not None:
                if existing != target:
                    raise ProviderCatalogDriftError(
                        "provider catalog target declaration "
                        "does not match persisted target: "
                        f"{target.target_id}"
                    )

                continue

            provider_model = (
                target.provider.provider_id,
                target.model.model_id,
            )
            aliased = existing_by_provider_model.get(
                provider_model
            )

            if aliased is not None:
                raise ProviderCatalogDriftError(
                    "provider catalog provider/model pair "
                    "already exists under a different target: "
                    f"{aliased.target_id}"
                )

        created_target_ids: list[str] = []

        for target in targets:
            if target.target_id in existing_by_id:
                continue

            try:
                persisted = self._catalog.create(
                    target
                )
            except Exception as exc:
                raise ProviderCatalogProvisioningError(
                    "provider catalog target provisioning failed: "
                    f"{target.target_id}"
                ) from exc

            if persisted != target:
                raise ProviderCatalogProvisioningError(
                    "provider catalog returned a persisted target "
                    "different from the declared target"
                )

            created_target_ids.append(
                target.target_id
            )

        return ProviderCatalogProvisioningResult(
            targets=targets,
            created_target_ids=tuple(
                created_target_ids
            ),
        )

    @staticmethod
    def _require_declarations(
        targets: tuple[ProviderModelTarget, ...],
    ) -> None:
        if not targets:
            raise ProviderCatalogDeclarationError(
                "provider catalog provisioning requires "
                "at least one target declaration"
            )

        target_ids = tuple(
            target.target_id
            for target in targets
        )

        if len(set(target_ids)) != len(
            target_ids
        ):
            raise ProviderCatalogDeclarationError(
                "provider catalog target declarations "
                "must have unique target IDs"
            )

        provider_models = tuple(
            (
                target.provider.provider_id,
                target.model.model_id,
            )
            for target in targets
        )

        if len(set(provider_models)) != len(
            provider_models
        ):
            raise ProviderCatalogDeclarationError(
                "provider catalog target declarations "
                "must have unique provider/model pairs"
            )
