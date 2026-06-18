package com.kaorisystem.auth.controller;

import com.kaorisystem.auth.model.WorkspaceKey;
import com.kaorisystem.auth.service.PlatformKeyService.GeneratedKey;
import com.kaorisystem.auth.service.PlatformKeyService.KeyNotFoundException;
import com.kaorisystem.auth.service.PlatformKeyService.RateLimitException;
import com.kaorisystem.auth.service.WorkspaceKeyService;
import com.kaorisystem.auth.service.WorkspaceKeyService.RevokedKey;
import com.kaorisystem.auth.service.WorkspaceMemberService;
import com.kaorisystem.auth.service.WorkspaceService;
import com.kaorisystem.auth.service.WorkspaceService.WorkspaceNotFoundException;
import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.autoconfigure.web.servlet.WebMvcTest;
import org.springframework.boot.test.mock.mockito.MockBean;
import org.springframework.http.MediaType;
import org.springframework.test.web.servlet.MockMvc;

import java.time.Instant;
import java.util.List;
import java.util.UUID;

import static org.hamcrest.Matchers.hasSize;
import static org.mockito.ArgumentMatchers.any;
import static org.mockito.ArgumentMatchers.anyString;
import static org.mockito.ArgumentMatchers.eq;
import static org.mockito.ArgumentMatchers.isNull;
import static org.mockito.BDDMockito.given;
import static org.mockito.BDDMockito.willThrow;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.delete;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.get;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.post;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.jsonPath;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.status;

/**
 * Web-layer slice for the F-009 nested key endpoints under
 * {@code /api/v1/platform/workspaces/{id}/keys}. Verifies the REST contract
 * (status codes, JSON shape, raw-key visibility) without booting the DB.
 */
@WebMvcTest(controllers = WorkspaceController.class,
            excludeAutoConfiguration = {
                org.springframework.boot.autoconfigure.security.servlet.SecurityAutoConfiguration.class
            })
@DisplayName("WorkspaceController keys — REST contract for /workspaces/{id}/keys")
class WorkspaceControllerKeysTest {

    @Autowired private MockMvc mockMvc;
    @MockBean  private WorkspaceService       workspaceService;
    @MockBean  private WorkspaceMemberService memberService;
    @MockBean  private WorkspaceKeyService    keyService;

    // -------------------------------------------------------------------------
    // GET /workspaces/{id}/keys
    // -------------------------------------------------------------------------

    @Test
    @DisplayName("GET — returns 200 with mapped keys (no raw_key field)")
    void list_happyPath() throws Exception {
        UUID wsId  = UUID.randomUUID();
        UUID keyId = UUID.randomUUID();
        Instant now = Instant.parse("2026-04-26T08:00:00Z");

        WorkspaceKey k = new WorkspaceKey();
        k.setKeyId(keyId);
        k.setWorkspaceId(wsId);
        k.setKeyHash("0".repeat(64));
        k.setLabel("prod");
        k.setCreatedAt(now);

        given(keyService.list(wsId)).willReturn(List.of(k));

        mockMvc.perform(get("/api/v1/platform/workspaces/" + wsId + "/keys"))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.data", hasSize(1)))
                .andExpect(jsonPath("$.data[0].key_id").value(keyId.toString()))
                .andExpect(jsonPath("$.data[0].label").value("prod"))
                .andExpect(jsonPath("$.data[0].status").value("active"))
                .andExpect(jsonPath("$.data[0].revoked_at").doesNotExist())
                .andExpect(jsonPath("$.data[0].raw_key").doesNotExist())
                .andExpect(jsonPath("$.data[0].key_hash").doesNotExist());
    }

    @Test
    @DisplayName("GET — unknown workspace returns 404")
    void list_unknownWorkspace() throws Exception {
        UUID wsId = UUID.randomUUID();
        willThrow(new WorkspaceNotFoundException("nope")).given(keyService).list(wsId);

        mockMvc.perform(get("/api/v1/platform/workspaces/" + wsId + "/keys"))
                .andExpect(status().isNotFound())
                .andExpect(jsonPath("$.title").value("Workspace not found"));
    }

    @Test
    @DisplayName("GET — invalid UUID in path returns 400")
    void list_invalidUuid() throws Exception {
        mockMvc.perform(get("/api/v1/platform/workspaces/not-a-uuid/keys"))
                .andExpect(status().isBadRequest())
                .andExpect(jsonPath("$.title").value("Invalid ID"));
    }

    // -------------------------------------------------------------------------
    // POST /workspaces/{id}/keys
    // -------------------------------------------------------------------------

    @Test
    @DisplayName("POST — happy path returns 201 with raw_key once + warning meta")
    void create_happyPath() throws Exception {
        UUID wsId  = UUID.randomUUID();
        UUID keyId = UUID.randomUUID();
        Instant now = Instant.parse("2026-04-26T08:00:00Z");

        given(keyService.generate(eq(wsId), eq("ci-runner"),
                isNull(), isNull(), anyString()))
                .willReturn(new GeneratedKey(keyId,
                        "KAORI-A3BQ7KXM-2YPC9NHR-DW4T6EJQ-8VFMCBLZ", "ci-runner", now));

        mockMvc.perform(post("/api/v1/platform/workspaces/" + wsId + "/keys")
                        .contentType(MediaType.APPLICATION_JSON)
                        .content("{\"label\":\"ci-runner\"}"))
                .andExpect(status().isCreated())
                .andExpect(jsonPath("$.data.key_id").value(keyId.toString()))
                .andExpect(jsonPath("$.data.raw_key")
                        .value("KAORI-A3BQ7KXM-2YPC9NHR-DW4T6EJQ-8VFMCBLZ"))
                .andExpect(jsonPath("$.data.label").value("ci-runner"))
                .andExpect(jsonPath("$.data.status").value("active"))
                .andExpect(jsonPath("$.data.revoked_at").value((Object) null))
                .andExpect(jsonPath("$.meta.warning").exists());
    }

    @Test
    @DisplayName("POST — empty body is accepted (label optional)")
    void create_emptyBody() throws Exception {
        UUID wsId  = UUID.randomUUID();
        UUID keyId = UUID.randomUUID();
        given(keyService.generate(eq(wsId), isNull(), isNull(), isNull(), anyString()))
                .willReturn(new GeneratedKey(keyId, "raw", null, Instant.now()));

        mockMvc.perform(post("/api/v1/platform/workspaces/" + wsId + "/keys")
                        .contentType(MediaType.APPLICATION_JSON)
                        .content("{}"))
                .andExpect(status().isCreated())
                .andExpect(jsonPath("$.data.label").value(""));
    }

    @Test
    @DisplayName("POST — unknown workspace returns 404")
    void create_unknownWorkspace() throws Exception {
        UUID wsId = UUID.randomUUID();
        willThrow(new WorkspaceNotFoundException("nope"))
                .given(keyService).generate(eq(wsId), any(), any(), any(), any());

        mockMvc.perform(post("/api/v1/platform/workspaces/" + wsId + "/keys")
                        .contentType(MediaType.APPLICATION_JSON)
                        .content("{}"))
                .andExpect(status().isNotFound())
                .andExpect(jsonPath("$.title").value("Workspace not found"));
    }

    @Test
    @DisplayName("POST — rate limit returns 429 with RFC 7807 body")
    void create_rateLimit() throws Exception {
        UUID wsId = UUID.randomUUID();
        willThrow(new RateLimitException("too many"))
                .given(keyService).generate(eq(wsId), any(), any(), any(), any());

        mockMvc.perform(post("/api/v1/platform/workspaces/" + wsId + "/keys")
                        .contentType(MediaType.APPLICATION_JSON)
                        .content("{}"))
                .andExpect(status().isTooManyRequests())
                .andExpect(jsonPath("$.status").value(429))
                .andExpect(jsonPath("$.title").value("Rate limit exceeded"));
    }

    @Test
    @DisplayName("POST — label > 100 chars returns 400")
    void create_labelTooLong() throws Exception {
        UUID wsId = UUID.randomUUID();
        String huge = "x".repeat(101);

        mockMvc.perform(post("/api/v1/platform/workspaces/" + wsId + "/keys")
                        .contentType(MediaType.APPLICATION_JSON)
                        .content("{\"label\":\"" + huge + "\"}"))
                .andExpect(status().isBadRequest());
    }

    // -------------------------------------------------------------------------
    // DELETE /workspaces/{id}/keys/{keyId}
    // -------------------------------------------------------------------------

    @Test
    @DisplayName("DELETE — happy path returns 200 with key_id + revoked status")
    void revoke_happyPath() throws Exception {
        UUID wsId  = UUID.randomUUID();
        UUID keyId = UUID.randomUUID();
        Instant now = Instant.parse("2026-04-26T08:30:00Z");

        given(keyService.revoke(eq(wsId), eq(keyId), any(), any(), anyString()))
                .willReturn(new RevokedKey(keyId, now));

        mockMvc.perform(delete("/api/v1/platform/workspaces/" + wsId + "/keys/" + keyId))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.data.key_id").value(keyId.toString()))
                .andExpect(jsonPath("$.data.status").value("revoked"))
                .andExpect(jsonPath("$.data.revoked_at").exists());
    }

    @Test
    @DisplayName("DELETE — unknown / cross-workspace key returns 404 (IDOR guard)")
    void revoke_keyNotFound() throws Exception {
        UUID wsId  = UUID.randomUUID();
        UUID keyId = UUID.randomUUID();
        willThrow(new KeyNotFoundException("not found"))
                .given(keyService).revoke(eq(wsId), eq(keyId), any(), any(), any());

        mockMvc.perform(delete("/api/v1/platform/workspaces/" + wsId + "/keys/" + keyId))
                .andExpect(status().isNotFound())
                .andExpect(jsonPath("$.title").value("Key not found"));
    }

    @Test
    @DisplayName("DELETE — unknown workspace returns 404")
    void revoke_unknownWorkspace() throws Exception {
        UUID wsId  = UUID.randomUUID();
        UUID keyId = UUID.randomUUID();
        willThrow(new WorkspaceNotFoundException("nope"))
                .given(keyService).revoke(eq(wsId), eq(keyId), any(), any(), any());

        mockMvc.perform(delete("/api/v1/platform/workspaces/" + wsId + "/keys/" + keyId))
                .andExpect(status().isNotFound())
                .andExpect(jsonPath("$.title").value("Workspace not found"));
    }

    @Test
    @DisplayName("DELETE — invalid keyId UUID returns 400")
    void revoke_invalidKeyId() throws Exception {
        UUID wsId = UUID.randomUUID();
        mockMvc.perform(delete("/api/v1/platform/workspaces/" + wsId + "/keys/not-a-uuid"))
                .andExpect(status().isBadRequest())
                .andExpect(jsonPath("$.title").value("Invalid ID"));
    }
}
