"use client";

import { useMutation, useQueryClient } from "@tanstack/react-query";
import { isAxiosError } from "axios";
import { useCallback, useState } from "react";
import { useDropzone } from "react-dropzone";

import { api } from "@/lib/api";

export function ScriptUploader({ batchId }: { batchId: string }) {
  const queryClient = useQueryClient();
  const [progress, setProgress] = useState<number | null>(null);
  const [error, setError] = useState<string | null>(null);

  const mutation = useMutation({
    mutationFn: async (files: File[]) => {
      const formData = new FormData();
      files.forEach((file) => formData.append("files", file));

      setProgress(0);
      await api.post(`/batches/${batchId}/scripts`, formData, {
        headers: { "Content-Type": "multipart/form-data" },
        onUploadProgress: (event) => {
          if (event.total) {
            setProgress(Math.round((event.loaded / event.total) * 100));
          }
        },
      });
    },
    onSuccess: async () => {
      setProgress(null);
      await queryClient.invalidateQueries({ queryKey: ["batch", batchId] });
    },
    onError: (err) => {
      setProgress(null);
      if (isAxiosError(err) && err.response) {
        setError(err.response.data?.detail ?? "Upload failed");
      } else {
        setError("Could not reach the server");
      }
    },
  });

  const onDrop = useCallback(
    (acceptedFiles: File[]) => {
      setError(null);
      if (acceptedFiles.length > 0) {
        mutation.mutate(acceptedFiles);
      }
    },
    [mutation]
  );

  const { getRootProps, getInputProps, isDragActive } = useDropzone({
    onDrop,
    accept: { "application/pdf": [".pdf"] },
    multiple: true,
    disabled: mutation.isPending,
  });

  return (
    <div className="mb-8">
      <div
        {...getRootProps()}
        className={`flex cursor-pointer flex-col items-center justify-center rounded-lg border-2 border-dashed px-6 py-10 text-center transition ${
          isDragActive ? "border-zinc-500 bg-zinc-50" : "border-zinc-300 bg-white"
        } ${mutation.isPending ? "cursor-not-allowed opacity-60" : ""}`}
      >
        <input {...getInputProps()} />
        <p className="text-sm font-medium text-zinc-700">
          {isDragActive
            ? "Drop the PDFs here…"
            : "Drag and drop scanned scripts (PDF), or click to select"}
        </p>
        <p className="mt-1 text-xs text-zinc-500">One or more PDF files, one per student.</p>
      </div>

      {progress !== null && (
        <div className="mt-3">
          <div className="h-2 w-full overflow-hidden rounded-full bg-zinc-200">
            <div
              className="h-full rounded-full bg-zinc-900 transition-all"
              style={{ width: `${progress}%` }}
            />
          </div>
          <p className="mt-1 text-xs text-zinc-500">Uploading… {progress}%</p>
        </div>
      )}

      {error && <p className="mt-2 text-sm text-red-600">{error}</p>}
    </div>
  );
}
