"use client";

import { useCallback, useEffect, useState } from "react";

import { apiFetch } from "@/lib/api-auth";

async function readApiErrorMessage(res: Response): Promise<string> {
  const text = await res.text();
  let msg = text || `HTTP ${res.status}`;
  try {
    const parsed = JSON.parse(text) as { detail?: unknown };
    if (typeof parsed.detail === "string") {
      msg = parsed.detail;
    } else if (Array.isArray(parsed.detail)) {
      msg = parsed.detail.map((d) => JSON.stringify(d)).join("; ");
    }
  } catch {
    /* keep raw text */
  }
  return msg;
}

type DocumentRow = {
  id: string;
  title: string;
  status: string;
  tags: string[];
  source_type: string;
  updated_at: string;
};

export function DocumentsPanel() {
  const [items, setItems] = useState<DocumentRow[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const [file, setFile] = useState<File | null>(null);
  const [title, setTitle] = useState("");
  const [tags, setTags] = useState("");
  const [uploading, setUploading] = useState(false);
  const [uploadMessage, setUploadMessage] = useState<string | null>(null);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const res = await apiFetch("/api/v1/documents?limit=50");
      if (!res.ok) {
        throw new Error(await readApiErrorMessage(res));
      }
      const data = (await res.json()) as { items: DocumentRow[] };
      setItems(data.items ?? []);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to load documents");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void load();
  }, [load]);

  async function onUpload(e: React.FormEvent) {
    e.preventDefault();
    if (!file) {
      setUploadMessage("Choose a file first (.txt or .pdf).");
      return;
    }
    setUploading(true);
    setUploadMessage(null);
    try {
      const form = new FormData();
      form.append("file", file);
      if (title.trim()) form.append("title", title.trim());
      if (tags.trim()) form.append("tags", tags.trim());
      form.append("source_type", "upload");

      const res = await apiFetch("/api/v1/documents/ingest", {
        method: "POST",
        body: form,
      });
      if (!res.ok) {
        throw new Error(await readApiErrorMessage(res));
      }
      await res.json();
      setUploadMessage("Upload complete. Your library will refresh in a moment.");
      setFile(null);
      setTitle("");
      setTags("");
      await load();
    } catch (err) {
      setUploadMessage(err instanceof Error ? err.message : "Upload failed");
    } finally {
      setUploading(false);
    }
  }

  return (
    <div className="space-y-8">
      <section className="rounded-lg border border-shell-border bg-shell-panel p-5">
        <h2 className="text-sm font-semibold text-zinc-100">Upload</h2>
        <p className="mt-1 text-sm text-shell-muted">
          Use plain text or PDF. We process the file so it can be searched and used in Copilot replies.
        </p>
        <form className="mt-4 space-y-3" onSubmit={(e) => void onUpload(e)}>
          <label className="block text-xs font-medium text-zinc-400">
            File
            <input
              type="file"
              accept=".txt,.md,.pdf,text/plain,application/pdf"
              className="mt-1 block w-full text-sm text-zinc-200 file:mr-3 file:rounded-md file:border file:border-shell-border file:bg-zinc-900 file:px-3 file:py-1.5 file:text-xs file:text-zinc-200"
              onChange={(e) => setFile(e.target.files?.[0] ?? null)}
            />
          </label>
          <label className="block text-xs font-medium text-zinc-400">
            Title (optional)
            <input
              value={title}
              onChange={(e) => setTitle(e.target.value)}
              className="mt-1 w-full rounded-md border border-shell-border bg-shell-bg px-3 py-2 text-sm text-zinc-100 outline-none focus:ring-2 focus:ring-shell-accent"
              placeholder="Defaults to filename"
            />
          </label>
          <label className="block text-xs font-medium text-zinc-400">
            Tags (optional, comma-separated)
            <input
              value={tags}
              onChange={(e) => setTags(e.target.value)}
              className="mt-1 w-full rounded-md border border-shell-border bg-shell-bg px-3 py-2 text-sm text-zinc-100 outline-none focus:ring-2 focus:ring-shell-accent"
              placeholder="billing, policy"
            />
          </label>
          <button
            type="submit"
            disabled={uploading}
            className="rounded-md bg-zinc-100 px-3 py-2 text-sm font-medium text-zinc-900 hover:opacity-90 disabled:cursor-not-allowed disabled:opacity-60"
          >
            {uploading ? "Uploading…" : "Upload"}
          </button>
          {uploadMessage ? (
            <p className="text-sm text-shell-muted" role="status">
              {uploadMessage}
            </p>
          ) : null}
        </form>
      </section>

      <section className="overflow-hidden rounded-lg border border-shell-border">
        <div className="border-b border-shell-border bg-shell-panel px-4 py-3">
          <h2 className="text-sm font-semibold text-zinc-100">Your documents</h2>
          <p className="text-xs text-shell-muted">Only you can see documents under your account.</p>
        </div>
        <table className="w-full text-left text-sm">
          <thead className="border-b border-shell-border bg-shell-bg text-xs uppercase tracking-wide text-zinc-500">
            <tr>
              <th className="px-4 py-3 font-medium">Title</th>
              <th className="px-4 py-3 font-medium">Status</th>
              <th className="px-4 py-3 font-medium">Tags</th>
              <th className="px-4 py-3 font-medium">Updated</th>
            </tr>
          </thead>
          <tbody>
            {loading ? (
              <tr>
                <td className="px-4 py-6 text-shell-muted" colSpan={4}>
                  Loading…
                </td>
              </tr>
            ) : error ? (
              <tr>
                <td className="px-4 py-6 text-red-400" colSpan={4}>
                  {error}
                </td>
              </tr>
            ) : items.length === 0 ? (
              <tr>
                <td className="px-4 py-6 text-shell-muted" colSpan={4}>
                  No documents yet. Upload a file above.
                </td>
              </tr>
            ) : (
              items.map((d) => (
                <tr key={d.id} className="border-b border-shell-border/60">
                  <td className="px-4 py-3 text-zinc-200">{d.title}</td>
                  <td className="px-4 py-3 text-shell-muted">{d.status}</td>
                  <td className="px-4 py-3 text-xs text-shell-muted">
                    {(d.tags ?? []).join(", ") || "—"}
                  </td>
                  <td className="px-4 py-3 text-xs text-shell-muted">
                    {new Date(d.updated_at).toLocaleString()}
                  </td>
                </tr>
              ))
            )}
          </tbody>
        </table>
      </section>
    </div>
  );
}
