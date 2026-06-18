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
  value: "deployment.environment={{ .Release.Namespace }}"
{{- end -}}

{{/*
Vault env vars — Phase 1.5+ services read secrets via VAULT_ADDR.
*/}}
{{- define "kaori-services.vaultEnv" -}}
- name: VAULT_ADDR
  value: {{ .Values.global.vaultAddr | quote }}
- name: VAULT_TOKEN
  valueFrom:
    secretKeyRef:
      name: vault-token
      key: token
      optional: true
{{- end -}}
