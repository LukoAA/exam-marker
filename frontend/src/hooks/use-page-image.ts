"use client";

import { useEffect, useState } from "react";

import { api } from "@/lib/api";

// GET /scripts/{id}/pages/{n}.png requires the Authorization header, so a
// plain <img src="..."> won't work (browsers don't attach custom headers to
// image requests). Fetch it as a blob through the authenticated axios client
// instead and hand back an object URL, revoking the previous one on change.
export function usePageImage(scriptId: string, pageNumber: number | null) {
  const [url, setUrl] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(false);

  useEffect(() => {
    if (pageNumber === null) {
      setUrl(null);
      return;
    }

    let cancelled = false;
    let objectUrl: string | null = null;

    setLoading(true);
    setError(false);
    setUrl(null);

    api
      .get(`/scripts/${scriptId}/pages/${pageNumber}.png`, { responseType: "blob" })
      .then((res) => {
        if (cancelled) return;
        objectUrl = URL.createObjectURL(res.data);
        setUrl(objectUrl);
      })
      .catch(() => {
        if (!cancelled) setError(true);
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });

    return () => {
      cancelled = true;
      if (objectUrl) URL.revokeObjectURL(objectUrl);
    };
  }, [scriptId, pageNumber]);

  return { url, loading, error };
}
