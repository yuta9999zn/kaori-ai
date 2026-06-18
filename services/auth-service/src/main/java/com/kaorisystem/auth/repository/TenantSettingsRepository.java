package com.kaorisystem.auth.repository;

import com.kaorisystem.auth.model.TenantSettings;
import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.data.jpa.repository.Query;
import org.springframework.data.repository.query.Param;

import java.util.Optional;
import java.util.UUID;

public interface TenantSettingsRepository extends JpaRepository<TenantSettings, UUID> {

    /**
     * Read-only descriptor pulled from `enterprises` so the F-016 settings
     * page can render `enterprise_name` + `locale` without owning a copy.
     * Locale lives on `enterprises` (001_init.sql:43) — see migration 015
     * for why we don't duplicate it into tenant_settings.
     */
    interface EnterpriseDescriptor {
        String  getName();
        String  getLocale();
    }

    @Query(value = """
            SELECT name AS name, locale AS locale
              FROM enterprises
             WHERE enterprise_id = :enterpriseId
            """, nativeQuery = true)
    Optional<EnterpriseDescriptor> findEnterpriseDescriptor(@Param("enterpriseId") UUID enterpriseId);
}
