{{/*
Expand the name of the chart.
*/}}
{{- define "kaori-services.name" -}}
{{- default .Chart.Name .Values.nameOverride | trunc 63 | trimSuffix "-" -}}
{{- end -}}

{{/*
Common labels — applied to every resource. K-19 + ops grep.
*/}}
{{- define "kaori-services.labels" -}}
app.kubernetes.io/managed-by: {{ .Release.Service }}
app.kubernetes.io/instance: {{ .Release.Name }}
helm.sh/chart: {{ printf "%s-%s" .Chart.Name .Chart.Version | replace "+" "_" }}
app.kubernetes.io/version: {{ .Chart.AppVersion | quote }}
app.kubernetes.io/part-of: kaori-ai
{{- end -}}

{{/*
Per-service labels — adds the service name + tier.
Usage: {{ include "kaori-services.serviceLabels" (dict "name" "auth-service" "root" .) }}
*/}}
{{- define "kaori-services.serviceLabels" -}}
{{ include "kaori-services.labels" .root }}
app.kubernetes.io/name: {{ .name }}
app.kubernetes.io/component: {{ .name }}
{{- end -}}

{{/*
Resolve image string from per-service config + global defaults.
*/}}
{{- define "kaori-services.image" -}}
{{- $registry := .root.Values.global.imageRegistry -}}
{{- $tag := default .root.Values.global.imageTag .service.image.tag -}}
{{- printf "%s/%s:%s" $registry .service.image.repository $tag -}}
{{- end -}}

{{/*
ServiceAccount name for a service. Falls back to a single shared SA
(global.serviceAccount.name) so IRSA annotations attach once; a service
can override with its own SA (e.g. data-pipeline needs the S3 IRSA role).
*/}}
{{- define "kaori-services.serviceAccountName" -}}
{{- $svc := .service -}}
{{- if and $svc.serviceAccount $svc.serviceAccount.name -}}
{{- $svc.serviceAccount.name -}}
{{- else -}}
{{- .root.Values.global.serviceAccount.name | default "kaori-services" -}}
{{- end -}}
{{- end -}}

{{/*
OpenTelemetry env vars added to every pod (K-19).
*/}}
{{- define "kaori-services.otelEnv" -}}
- name: OTEL_EXPORTER_OTLP_ENDPOINT
  value: {{ .Values.global.otlpEndpoint | quote }}
- name: OTEL_TRACES_SAMPLER
  value: traceidratio
- name: OTEL_TRACES_SAMPLER_ARG
  value: {{ .Values.global.tracingSampleRate | quote }}
- name: OTEL_RESOURCE_ATTRIBUTES
  value: "deployment.environment={{ .Release.Namespace }},service.name={{ .name }}"
{{- end -}}

{{/*
Shared datastore / platform env, common to EVERY service. Reads
connection endpoints from global.datastore + global.blob so an env
overlay (values-aws-eks.yaml) can repoint Postgres → RDS, Redis →
ElastiCache, Kafka → MSK, blob → S3 by overriding globals ONCE instead
of editing every per-service env block (explicit-over-implicit, tenet #4).

Secrets (DB password, JWT keys, MFA/field keys, API keys) are pulled by
secretKeyRef from the shared Secret so plaintext never lands in a
ConfigMap or values.yaml (red-team C2). Missing keys surface per
global.secrets.optional: dev leaves it true (render without secrets),
production overlays set it false so a missing key fails loud (K-18, C1).
*/}}
{{- define "kaori-services.commonEnv" -}}
{{- $ds := .Values.global.datastore -}}
{{- $blob := .Values.global.blob -}}
{{- $secretOptional := .Values.global.secrets.optional -}}
- name: KAORI_PROFILE
  value: {{ .Values.global.profile | quote }}
- name: VAULT_ADDR
  value: {{ .Values.global.vaultAddr | quote }}
- name: KAFKA_BOOTSTRAP_SERVERS
  value: {{ $ds.kafkaBootstrap | quote }}
- name: BLOB_STORE_BACKEND
  value: {{ $blob.backend | quote }}
{{- if eq $blob.backend "local" }}
- name: BLOB_STORE_PATH
  value: {{ $blob.path | quote }}
{{- else if eq $blob.backend "s3" }}
- name: S3_BUCKET
  value: {{ $blob.s3Bucket | quote }}
- name: S3_REGION
  value: {{ $blob.s3Region | quote }}
{{- if $blob.s3Endpoint }}
- name: S3_ENDPOINT
  value: {{ $blob.s3Endpoint | quote }}
{{- end }}
{{- end }}
- name: VAULT_TOKEN
  valueFrom:
    secretKeyRef:
      name: {{ .Values.global.secrets.name | default "kaori-shared-secret" }}
      key: vault-token
      optional: {{ $secretOptional }}
{{- end -}}

{{/*
Python-service datastore env — DATABASE_URL + REDIS_URL built from
globals, DB password from the shared Secret.
*/}}
{{- define "kaori-services.pythonEnv" -}}
{{- $ds := .Values.global.datastore -}}
{{- $secretOptional := .Values.global.secrets.optional -}}
- name: DATABASE_URL
  value: {{ printf "postgresql://%s@%s:%v/%s" $ds.appUser $ds.postgresHost (toString $ds.postgresPort) $ds.postgresDb | quote }}
- name: REDIS_URL
  value: {{ $ds.redisUrl | quote }}
{{- end -}}

{{/*
Java-service datastore env — Spring wants SPRING_DATASOURCE_* / R2DBC /
REDIS_HOST rather than a single URL. Password/user come from the shared
Secret; the Flyway superuser path is set per-service in values.yaml.
*/}}
{{- define "kaori-services.javaEnv" -}}
{{- $ds := .Values.global.datastore -}}
{{- $secretOptional := .Values.global.secrets.optional -}}
- name: SPRING_DATASOURCE_URL
  value: {{ printf "jdbc:postgresql://%s:%v/%s" $ds.postgresHost (toString $ds.postgresPort) $ds.postgresDb | quote }}
- name: SPRING_R2DBC_URL
  value: {{ printf "r2dbc:postgresql://%s:%v/%s" $ds.postgresHost (toString $ds.postgresPort) $ds.postgresDb | quote }}
- name: SPRING_DATASOURCE_USERNAME
  value: {{ $ds.appUser | quote }}
- name: SPRING_R2DBC_USERNAME
  value: {{ $ds.appUser | quote }}
- name: SPRING_REDIS_HOST
  value: {{ $ds.redisHost | quote }}
- name: REDIS_HOST
  value: {{ $ds.redisHost | quote }}
- name: SPRING_DATASOURCE_PASSWORD
  valueFrom:
    secretKeyRef:
      name: {{ .Values.global.secrets.name | default "kaori-shared-secret" }}
      key: app-db-password
      optional: {{ $secretOptional }}
- name: SPRING_R2DBC_PASSWORD
  valueFrom:
    secretKeyRef:
      name: {{ .Values.global.secrets.name | default "kaori-shared-secret" }}
      key: app-db-password
      optional: {{ $secretOptional }}
{{- end -}}

{{/*
Pod-level securityContext (fsGroup + non-root + seccomp). Rendered only
when global.securityContext.enabled. EKS namespaces under the
Pod Security Standards `restricted` profile reject root containers;
this makes every Kaori pod compliant (red-team B6).
*/}}
{{- define "kaori-services.podSecurityContext" -}}
runAsNonRoot: true
runAsUser: {{ .Values.global.securityContext.runAsUser | default 10001 }}
runAsGroup: {{ .Values.global.securityContext.runAsGroup | default 10001 }}
fsGroup: {{ .Values.global.securityContext.fsGroup | default 10001 }}
seccompProfile:
  type: RuntimeDefault
{{- end -}}

{{/*
Container-level securityContext — drop all caps, no privilege escalation.
readOnlyRootFilesystem is opt-in per service (Java writes a temp dir).
*/}}
{{- define "kaori-services.containerSecurityContext" -}}
allowPrivilegeEscalation: false
privileged: false
capabilities:
  drop:
    - ALL
readOnlyRootFilesystem: {{ .service.readOnlyRootFilesystem | default false }}
{{- end -}}
