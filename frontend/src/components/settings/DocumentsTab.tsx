import { useState, useEffect, useCallback } from 'react';
import { FileText, X, RefreshCw } from 'lucide-react';
import { Button, Card, Badge, AlertBanner, PageLoadingState } from '../common';
import { adminApi } from '../../services/api';
import { getApiErrorMessage } from '../../utils/errors';
import type { SettingsDocumentEntry } from '../../types';

export function DocumentsTab() {
  const [list, setList] = useState<SettingsDocumentEntry[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [previewPath, setPreviewPath] = useState<string | null>(null);
  const [previewType, setPreviewType] = useState<'pdf' | 'docx' | null>(null);
  const [previewContent, setPreviewContent] = useState<string | null>(null);
  const [previewBlobUrl, setPreviewBlobUrl] = useState<string | null>(null);
  const [previewLoading, setPreviewLoading] = useState(false);

  const fetchList = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const data = await adminApi.getDocumentsList();
      setList(Array.isArray(data) ? data : []);
    } catch (e) {
      setError(getApiErrorMessage(e));
      setList([]);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchList();
  }, [fetchList]);

  const openPreview = useCallback(async (doc: SettingsDocumentEntry) => {
    setPreviewPath(doc.path);
    setPreviewType(doc.type);
    setPreviewContent(null);
    setPreviewBlobUrl(null);
    setPreviewLoading(true);
    try {
      const blob = await adminApi.getDocumentPreview(doc.path);
      if (doc.type === 'pdf') {
        const url = URL.createObjectURL(blob);
        setPreviewBlobUrl(url);
      } else {
        const url = URL.createObjectURL(blob);
        setPreviewBlobUrl(url);
      }
    } catch {
      setPreviewContent('Failed to load preview.');
    } finally {
      setPreviewLoading(false);
    }
  }, []);

  const closePreview = useCallback(() => {
    if (previewBlobUrl) URL.revokeObjectURL(previewBlobUrl);
    setPreviewPath(null);
    setPreviewType(null);
    setPreviewContent(null);
    setPreviewBlobUrl(null);
  }, [previewBlobUrl]);

  useEffect(() => {
    return () => {
      if (previewBlobUrl) URL.revokeObjectURL(previewBlobUrl);
    };
  }, [previewBlobUrl]);

  useEffect(() => {
    if (previewPath === null) return;
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === 'Escape') closePreview();
    };
    document.addEventListener('keydown', handleKeyDown);
    return () => document.removeEventListener('keydown', handleKeyDown);
  }, [previewPath, closePreview]);

  if (loading) {
    return <PageLoadingState />;
  }

  return (
    <div className="space-y-6">
      {error && (
        <AlertBanner variant="error" message={error} onDismiss={() => setError(null)} className="mb-4" />
      )}

      <Card className="bg-navy-800/50 border-navy-700" data-testid="settings-documents-card">
        <div className="flex items-center justify-between mb-6">
          <h2 className="text-xl font-bold text-white flex items-center gap-2">
            <FileText className="w-5 h-5 text-blue-500" />
            Documentation (documents/)
          </h2>
          <Button variant="outline" size="sm" onClick={fetchList} icon={<RefreshCw className="w-4 h-4" />}>
            Refresh
          </Button>
        </div>
        <p className="text-sm text-navy-400 mb-6">
          Platform documents from the repo <code className="text-navy-300">documents/</code> folder. Used = in Document Library or attached to an email template; <strong>(NU)</strong> = not used.
        </p>

        {list.length === 0 ? (
          <p className="text-sm text-navy-400">No documents found.</p>
        ) : (
          <div className="space-y-4">
            {list.map((doc) => (
              <div
                key={doc.path}
                className="rounded-xl p-4 border border-navy-700 bg-navy-700/30 flex flex-col sm:flex-row sm:items-center sm:justify-between gap-3"
              >
                <div className="min-w-0 flex-1">
                  <div className="flex items-center gap-2 flex-wrap">
                    <span className="text-sm font-semibold text-white truncate">{doc.name}</span>
                    {!doc.used && (
                      <Badge variant="navy" className="text-amber-400 bg-amber-500/20 shrink-0">
                        NU
                      </Badge>
                    )}
                    <span className="text-xs text-navy-500 font-mono truncate">{doc.path}</span>
                  </div>
                  {(doc.title ?? doc.phaseName ?? doc.category) && (
                    <div className="text-xs text-navy-400 mt-1">
                      {doc.title && <span className="text-navy-300">{doc.title}</span>}
                      {doc.phaseName && (
                        <span className="ml-2">
                          <span className="uppercase tracking-wider text-navy-500">Phase</span>{' '}
                          <span className="text-navy-300">{doc.phaseName}</span>
                        </span>
                      )}
                      {doc.category && (
                        <span className="ml-2">
                          <span className="uppercase tracking-wider text-navy-500">Category</span>{' '}
                          <span className="text-navy-300">{doc.category}</span>
                        </span>
                      )}
                    </div>
                  )}
                  <div className="flex flex-wrap gap-2 mt-2">
                    <span className="text-xs uppercase tracking-wider text-navy-400">Email templates</span>
                    {(doc.emailTemplates ?? [])?.length ? (
                      <span className="flex flex-wrap gap-1">
                        {doc.emailTemplates.map((t) => (
                          <Badge key={t} variant="navy" className="text-xs">
                            {t}
                          </Badge>
                        ))}
                      </span>
                    ) : (
                      <span className="text-sm text-navy-300">—</span>
                    )}
                  </div>
                </div>
                <Button
                  variant="outline"
                  size="sm"
                  onClick={() => openPreview(doc)}
                  className="flex-shrink-0"
                >
                  Preview
                </Button>
              </div>
            ))}
          </div>
        )}
      </Card>

      {/* Preview modal */}
      {(previewPath !== null && previewType !== null) && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/60" onClick={closePreview}>
          <div
            className="bg-navy-800 border border-navy-700 rounded-2xl shadow-xl w-full max-w-4xl max-h-[90vh] flex flex-col"
            onClick={(e) => e.stopPropagation()}
          >
            <div className="flex items-center justify-between p-4 border-b border-navy-700">
              <span className="text-sm font-medium text-navy-200 truncate">{previewPath}</span>
              <button
                type="button"
                onClick={closePreview}
                className="p-1.5 rounded hover:bg-navy-700 text-navy-400 hover:text-white transition-colors"
                aria-label="Close preview"
              >
                <X className="w-5 h-5" />
              </button>
            </div>
            <div className="flex-1 min-h-0 overflow-hidden p-4">
              {previewLoading ? (
                <p className="text-sm text-navy-400">Loading…</p>
              ) : previewType === 'pdf' && previewBlobUrl ? (
                <iframe
                  src={previewBlobUrl}
                  title={previewPath ?? undefined}
                  className="w-full h-full min-h-[70vh] rounded-lg border border-navy-700 bg-white"
                />
              ) : previewType === 'docx' && previewBlobUrl ? (
                <p className="text-sm text-navy-400">
                  .docx file — <a href={previewBlobUrl} download className="text-emerald-400 hover:underline">Download</a>
                </p>
              ) : previewContent !== null ? (
                <pre className="w-full h-full min-h-[70vh] overflow-auto rounded-lg border border-navy-700 bg-navy-900 p-4 text-xs text-navy-200 font-mono whitespace-pre-wrap">
                  {previewContent}
                </pre>
              ) : null}
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
