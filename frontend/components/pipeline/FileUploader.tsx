"use client";

import { useState, useCallback } from "react";
import { useDropzone } from "react-dropzone";
import { Upload, FileSpreadsheet, FileText, CheckCircle2, XCircle, Loader2, AlertCircle } from "lucide-react";
import { pipelineApi } from "@/lib/api/client";
import { Card, CardContent } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Progress } from "@/components/ui/progress";

const ACCEPTED_TYPES = {
  "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet": [".xlsx"],
  "application/vnd.ms-excel": [".xls", ".xlsm", ".xlsb"],
  "text/csv": [".csv"],
  "text/tab-separated-values": [".tsv"],
  "application/vnd.oasis.opendocument.spreadsheet": [".ods"],
  "application/zip": [".zip"],
  "application/sql": [".sql"],
  "text/plain": [".txt"],
};

type UploadStatus = "idle" | "uploading" | "processing" | "done" | "error";

interface FileUpload {
  file: File;
  runId: string | null;
  status: UploadStatus;
  progress: number;
  error?: string;
}

function fileIcon(name: string) {
  const ext = name.split(".").pop()?.toLowerCase();
  if (["xlsx","xls","xlsm","xlsb","ods"].includes(ext ?? "")) return FileSpreadsheet;
  return FileText;
}

export default function FileUploader({ onComplete }: { onComplete: (runId: string) => void }) {
  const [uploads, setUploads]       = useState<FileUpload[]>([]);
  const [globalError, setGlobalError] = useState("");

  function updateUpload(idx: number, patch: Partial<FileUpload>) {
    setUploads((prev) => prev.map((u, i) => (i === idx ? { ...u, ...patch } : u)));
  }

  async function processFile(file: File, idx: number) {
    updateUpload(idx, { status: "uploading", progress: 10 });
    try {
      const { data } = await pipelineApi.upload(file);
      const runId = data.run_id;
      updateUpload(idx, { runId, status: "processing", progress: 40 });

      let attempts = 0;
      while (attempts < 60) {
        await new Promise((r) => setTimeout(r, 2000));
        const { data: status } = await pipelineApi.getStatus(runId);
        updateUpload(idx, { progress: 40 + Math.min(attempts * 2, 55) });

        if (status.status === "bronze_complete" || status.status === "schema_review") {
          updateUpload(idx, { status: "done", progress: 100 });
          onComplete(runId);
          return;
        }
        if (status.status === "failed") throw new Error(status.error_message || "Pipeline failed");
        if (status.status === "duplicate") { updateUpload(idx, { status: "done", progress: 100 }); onComplete(runId); return; }
        attempts++;
      }
      throw new Error("Upload timed out");
    } catch (err: unknown) {
      updateUpload(idx, { status: "error", error: (err as Error).message || "Upload failed", progress: 0 });
    }
  }

  const onDrop = useCallback((acceptedFiles: File[]) => {
    setGlobalError("");
    const startIdx = uploads.length;
    const newUploads = acceptedFiles.map((f) => ({ file: f, runId: null, status: "idle" as UploadStatus, progress: 0 }));
    setUploads((prev) => [...prev, ...newUploads]);
    newUploads.forEach((_, i) => processFile(acceptedFiles[i], startIdx + i));
  }, [uploads]);

  const { getRootProps, getInputProps, isDragActive } = useDropzone({
    onDrop,
    accept: ACCEPTED_TYPES,
    maxSize: 100 * 1024 * 1024,
    onDropRejected: (rejections) => {
      setGlobalError(rejections.map((r) => r.errors.map((e) => e.message).join(", ")).join("; "));
    },
  });

  return (
    <div className="space-y-6">
      <div>
        <h2 className="text-h2 font-serif text-[#2E2A24]">Tải lên dữ liệu</h2>
        <p className="text-small text-[#7A7266] mt-1">
          Hỗ trợ: Excel (.xlsx, .xls), CSV, TSV, ODS, ZIP, SQL — tối đa 100 MB/file
        </p>
      </div>

      {/* Drop zone */}
      <div
        {...getRootProps()}
        className={`border-2 border-dashed rounded-2xl p-14 text-center cursor-pointer transition-colors ${
          isDragActive
            ? "border-brand-400 bg-brand-50"
            : "border-subtle bg-surface hover:border-brand-300 hover:bg-brand-50/40"
        }`}
      >
        <input {...getInputProps()} />
        <Upload className={`w-9 h-9 mx-auto mb-4 ${isDragActive ? "text-brand-500" : "text-[#C0B8A8]"}`} strokeWidth={1.5} />
        <p className="text-body-strong text-[#2E2A24]">
          {isDragActive ? "Thả file vào đây…" : "Kéo thả file hoặc nhấp để chọn"}
        </p>
        <p className="text-small text-[#A89F90] mt-1.5">
          Excel, CSV, TSV, ODS, ZIP, SQL · tối đa 100 MB
        </p>
      </div>

      {globalError && (
        <div className="flex items-center gap-2 bg-danger-50 border border-danger-100 rounded-xl px-4 py-3">
          <AlertCircle className="w-4 h-4 text-danger-500 shrink-0" />
          <p className="text-small text-danger-700">{globalError}</p>
        </div>
      )}

      {/* Upload list */}
      {uploads.length > 0 && (
        <div className="space-y-3">
          {uploads.map((u, i) => {
            const FileIcon = fileIcon(u.file.name);
            return (
              <Card key={i}>
                <CardContent className="py-4 flex items-center gap-4">
                  <div className={`p-2.5 rounded-xl shrink-0 ${
                    u.status === "done"  ? "bg-success-50 text-success-600" :
                    u.status === "error" ? "bg-danger-50  text-danger-600"  :
                                           "bg-brand-50   text-brand-500"
                  }`}>
                    {u.status === "done"  ? <CheckCircle2 className="w-5 h-5" /> :
                     u.status === "error" ? <XCircle      className="w-5 h-5" /> :
                     (u.status === "uploading" || u.status === "processing")
                                          ? <Loader2 className="w-5 h-5 animate-spin" /> :
                                            <FileIcon className="w-5 h-5" strokeWidth={1.5} />}
                  </div>

                  <div className="flex-1 min-w-0 space-y-1.5">
                    <div className="flex items-center justify-between gap-3">
                      <p className="text-body-strong text-[#2E2A24] truncate">{u.file.name}</p>
                      <Badge tone={
                        u.status === "done"       ? "success" :
                        u.status === "error"      ? "danger"  :
                        u.status === "uploading"  ? "info"    :
                        u.status === "processing" ? "brand"   : "neutral"
                      }>
                        {u.status === "uploading"  ? "Đang tải…"  :
                         u.status === "processing" ? "Đang xử lý…":
                         u.status === "done"       ? "Hoàn tất"   :
                         u.status === "error"      ? "Lỗi"        : "Chờ"}
                      </Badge>
                    </div>

                    <p className="text-tiny text-[#A89F90]">
                      {(u.file.size / 1024 / 1024).toFixed(1)} MB
                    </p>

                    {u.status !== "idle" && u.status !== "done" && u.status !== "error" && (
                      <Progress value={u.progress} tone="brand" className="h-1" />
                    )}

                    {u.error && (
                      <p className="text-tiny text-danger-600">{u.error}</p>
                    )}
                  </div>
                </CardContent>
              </Card>
            );
          })}
        </div>
      )}
    </div>
  );
}
