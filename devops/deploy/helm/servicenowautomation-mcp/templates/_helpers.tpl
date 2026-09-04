{{/* vim: set filetype=mustache: */}}
{{/*
Expand the name of the chart.
*/}}
{{- define "servicenowautomation-mcp.name" -}}
{{- default .Chart.Name .Values.nameOverride | trunc 63 | trimSuffix "-" }}
{{- end }}

{{/*
Create a default fully qualified app name.
We truncate at 63 chars because some Kubernetes name fields are limited to this (by the DNS naming spec).
If release name contains chart name it will be used as a full name.
*/}}
{{- define "servicenowautomation-mcp.fullname" -}}
{{- if .Values.fullnameOverride }}
{{- .Values.fullnameOverride | trunc 63 | trimSuffix "-" }}
{{- else }}
{{- $name := default .Chart.Name .Values.nameOverride }}
{{- if contains $name .Release.Name }}
{{- .Release.Name | trunc 63 | trimSuffix "-" }}
{{- else }}
{{- printf "%s-%s" .Release.Name $name | trunc 63 | trimSuffix "-" }}
{{- end }}
{{- end }}
{{- end }}

{{/*
Create chart name and version as used by the chart label.
*/}}
{{- define "servicenowautomation-mcp.chart" -}}
{{- printf "%s-%s" .Chart.Name .Chart.Version | replace "+" "_" | trunc 63 | trimSuffix "-" }}
{{- end }}

{{/*
Common labels
*/}}
{{- define "servicenowautomation-mcp.labels" -}}
helm.sh/chart: {{ include "servicenowautomation-mcp.chart" . }}
{{ include "servicenowautomation-mcp.selectorLabels" . }}
{{- if .Chart.AppVersion }}
app.kubernetes.io/version: {{ .Chart.AppVersion | quote }}
{{- end }}
app.kubernetes.io/managed-by: {{ .Release.Service }}
{{- end }}

{{/*
Selector labels
*/}}
{{- define "servicenowautomation-mcp.selectorLabels" -}}
app.kubernetes.io/name: {{ include "servicenowautomation-mcp.name" . }}
app.kubernetes.io/instance: {{ .Release.Name }}
{{- end }}

{{/*
Create the name of the service account to use
*/}}
{{- define "servicenowautomation-mcp.serviceAccountName" -}}
{{- if .Values.serviceAccount.create }}
{{- default (include "servicenowautomation-mcp.fullname" .) .Values.serviceAccount.name }}
{{- else }}
{{- default "default" .Values.serviceAccount.name }}
{{- end }}
{{- end }}

{{/*
Cert thumbprint
*/}}
{{- define "servicenowautomation-mcp.certThumbprint" -}}
{{- if contains ";" .Values.certThumbprints -}}
    {{- $certList := splitList ";" .Values.certThumbprints -}}
    {{- range $k, $v := $certList -}}
        {{- if eq (len $certList) (add $k 1) -}}
            {{- printf . -}}
        {{- else -}}
            {{- printf "%s%s"  . "\" and thumbprintcert ~= \"" -}}
        {{- end -}}
    {{- end -}}
{{- else -}}
    {{- .Values.certThumbprints -}}
{{- end -}}
{{- end -}}

{{/*
Auth Policy
*/}}
{{- define "servicenowautomation-mcp.authpolicy" -}}
{{- if .Values.authpolicylist -}}
    {{- if contains ";" .Values.authpolicylist -}}
        {{- $authList := splitList ";" .Values.authpolicylist -}}
        {{- range $k, $v := $authList -}} 
            {{- $authItem := splitList "_" . -}} 
                {{- printf "%s%s%s%s"  ", cluster.local/ns/" (first $authItem) "/sa/" (last $authItem)  -}} 
        {{- end -}}
    {{- else -}}
        {{- $authItem := splitList "_" .Values.authpolicylist -}} 
            {{- printf "%s%s%s%s"  ", cluster.local/ns/" (first $authItem) "/sa/" (last $authItem)  -}}
    {{- end -}}
{{- else -}}
{{- printf "" -}}
{{- end -}}
{{- end -}}