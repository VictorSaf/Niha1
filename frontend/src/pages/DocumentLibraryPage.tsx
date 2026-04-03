import { useState, useEffect, useMemo } from 'react';
import { Zap, Users } from 'lucide-react';
import { documentLibraryApi } from '../services/api';
import type { PlatformDocument, DocumentPhaseInfo, DocumentCategory, DocumentPhase } from '../types';
import { useAuthStore } from '../stores/useStore';

// Phase colors (no icons – professional layout)
const PHASE_CONFIG: Record<string, { color: string; bg: string; label: string }> = {
  F0: { color: 'text-navy-300', bg: 'bg-navy-700/50', label: 'Internal' },
  F1: { color: 'text-blue-400', bg: 'bg-blue-500/10', label: 'NDA' },
  F2: { color: 'text-amber-400', bg: 'bg-amber-500/10', label: 'KYC' },
  F3: { color: 'text-emerald-400', bg: 'bg-emerald-500/10', label: 'Contracts' },
  F4: { color: 'text-blue-300', bg: 'bg-blue-400/10', label: 'Funding' },
  F5: { color: 'text-emerald-300', bg: 'bg-emerald-400/10', label: 'Trading' },
  F6: { color: 'text-amber-300', bg: 'bg-amber-400/10', label: 'Reports' },
  F7: { color: 'text-navy-400', bg: 'bg-navy-600/30', label: 'Reference' },
};

const CATEGORY_CONFIG: Record<DocumentCategory, { color: string; label: string }> = {
  legal: { color: 'text-blue-400 bg-blue-500/20', label: 'Legal' },
  compliance: { color: 'text-amber-400 bg-amber-500/20', label: 'Compliance' },
  operational: { color: 'text-emerald-400 bg-emerald-500/20', label: 'Operational' },
  trading: { color: 'text-emerald-300 bg-emerald-400/20', label: 'Trading' },
  reporting: { color: 'text-blue-300 bg-blue-400/20', label: 'Reporting' },
  internal: { color: 'text-navy-300 bg-navy-500/20', label: 'Internal' },
};

export default function DocumentLibraryPage() {
  const [documents, setDocuments] = useState<PlatformDocument[]>([]);
  const [phases, setPhases] = useState<DocumentPhaseInfo[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [selectedPhase, setSelectedPhase] = useState<DocumentPhase | 'ALL'>('ALL');
  const [selectedCategory, setSelectedCategory] = useState<DocumentCategory | 'ALL'>('ALL');
  const [searchQuery, setSearchQuery] = useState('');
  const [downloading, setDownloading] = useState<string | null>(null);
  const [downloadError, setDownloadError] = useState<string | null>(null);
  const { user } = useAuthStore();

  useEffect(() => {
    loadDocuments();
  }, []);

  const loadDocuments = async () => {
    try {
      setLoading(true);
      setError(null);
      const response = await documentLibraryApi.getLibrary();
      setDocuments(response.documents);
      setPhases(response.phases);
    } catch (err: unknown) {
      const message = err instanceof Error ? err.message : 'Failed to load documents';
      setError(message);
    } finally {
      setLoading(false);
    }
  };

  const filteredDocuments = useMemo(() => {
    let docs = documents;
    if (selectedPhase !== 'ALL') {
      docs = docs.filter(d => d.phase === selectedPhase);
    }
    if (selectedCategory !== 'ALL') {
      docs = docs.filter(d => d.category === selectedCategory);
    }
    if (searchQuery.trim()) {
      const q = searchQuery.toLowerCase();
      docs = docs.filter(d =>
        d.title.toLowerCase().includes(q) ||
        d.description.toLowerCase().includes(q)
      );
    }
    return docs;
  }, [documents, selectedPhase, selectedCategory, searchQuery]);

  // Group by phase
  const groupedDocuments = useMemo(() => {
    const groups: Record<string, PlatformDocument[]> = {};
    for (const doc of filteredDocuments) {
      if (!groups[doc.phase]) groups[doc.phase] = [];
      groups[doc.phase].push(doc);
    }
    return groups;
  }, [filteredDocuments]);

  const handleDownload = async (doc: PlatformDocument) => {
    setDownloadError(null);
    try {
      setDownloading(doc.id);
      const { blob, filename } = await documentLibraryApi.downloadDocument(doc.id);
      const url = window.URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = filename ?? doc.filename;
      document.body.appendChild(a);
      a.click();
      window.URL.revokeObjectURL(url);
      document.body.removeChild(a);
    } catch (err: unknown) {
      const msg =
        err && typeof err === 'object' && 'message' in err && typeof (err as { message: string }).message === 'string'
          ? (err as { message: string }).message
          : 'Download failed. Please try again.';
      setDownloadError(msg);
    } finally {
      setDownloading(null);
    }
  };

  const uniqueCategories = useMemo(() => {
    const cats = new Set(documents.map(d => d.category));
    return Array.from(cats) as DocumentCategory[];
  }, [documents]);

  if (loading) {
    return (
      <div className="min-h-screen bg-navy-900 flex items-center justify-center">
        <div className="flex flex-col items-center gap-3">
          <div className="w-8 h-8 border-2 border-emerald-400 border-t-transparent rounded-full animate-spin" />
          <p className="text-navy-300 text-sm">Loading document library...</p>
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="min-h-screen bg-navy-900 flex items-center justify-center">
        <div className="bg-navy-800 border border-navy-700 rounded-lg p-6 max-w-md text-center">
          <p className="text-red-400 mb-4">{error}</p>
          <button
            onClick={loadDocuments}
            className="px-4 py-2 bg-emerald-500/20 text-emerald-400 rounded hover:bg-emerald-500/30 transition-colors text-sm"
          >
            Retry
          </button>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-navy-900 relative">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
        {/* Header */}
        <div className="mb-8">
          <h1 className="text-2xl font-semibold text-white mb-2">
            Document Library
          </h1>
          <p className="text-navy-300 text-sm">
            {documents.length} document{documents.length !== 1 ? 's' : ''} available for your current role
            {user?.role && (
              <span className="ml-2 px-2 py-0.5 bg-navy-700 rounded text-xs text-navy-200">
                {user.role}
              </span>
            )}
          </p>
        </div>

        {/* Download error banner */}
        {downloadError && (
          <div className="mb-6 rounded-lg border-2 border-amber-500/40 bg-amber-500/10 p-4 flex items-start justify-between gap-4">
            <p className="text-amber-300 text-sm flex-1">{downloadError}</p>
            <button
              type="button"
              onClick={() => setDownloadError(null)}
              className="flex-shrink-0 text-navy-400 hover:text-white transition-colors text-sm"
              aria-label="Dismiss"
            >
              ✕
            </button>
          </div>
        )}

        {/* Filters */}
        <div className="bg-navy-800/50 border border-navy-700 rounded-lg p-4 mb-6">
          <div className="flex flex-wrap gap-4 items-center">
            {/* Search */}
            <div className="flex-1 min-w-[200px]">
              <input
                type="text"
                placeholder="Search documents..."
                value={searchQuery}
                onChange={e => setSearchQuery(e.target.value)}
                className="w-full bg-navy-900 border border-navy-600 rounded px-3 py-2 text-sm text-white placeholder-navy-500 focus:outline-none focus:border-emerald-500/50"
              />
            </div>

            {/* Phase filter */}
            <div className="flex items-center gap-2">
              <span className="text-navy-400 text-xs uppercase tracking-wider">Phase:</span>
              <select
                value={selectedPhase}
                onChange={e => setSelectedPhase(e.target.value as DocumentPhase | 'ALL')}
                className="select-arrow-spaced"
              >
                <option value="ALL">All Phases</option>
                {phases.map(p => (
                  <option key={p.code} value={p.code}>
                    {p.code} — {p.name}
                  </option>
                ))}
              </select>
            </div>

            {/* Category filter */}
            <div className="flex items-center gap-2">
              <span className="text-navy-400 text-xs uppercase tracking-wider">Category:</span>
              <select
                value={selectedCategory}
                onChange={e => setSelectedCategory(e.target.value as DocumentCategory | 'ALL')}
                className="select-arrow-spaced"
              >
                <option value="ALL">All Categories</option>
                {uniqueCategories.map(cat => (
                  <option key={cat} value={cat}>
                    {CATEGORY_CONFIG[cat]?.label || cat}
                  </option>
                ))}
              </select>
            </div>
          </div>
        </div>

        {/* Results count */}
        {(selectedPhase !== 'ALL' || selectedCategory !== 'ALL' || searchQuery) && (
          <p className="text-navy-400 text-sm mb-4">
            Showing {filteredDocuments.length} of {documents.length} documents
            {searchQuery && <span className="ml-1">matching &quot;{searchQuery}&quot;</span>}
          </p>
        )}

        {/* Documents grouped by phase */}
        {filteredDocuments.length === 0 ? (
          <div className="text-center py-12">
            <p className="text-navy-400">No documents match your filters.</p>
          </div>
        ) : (
          <div className="space-y-8">
            {Object.entries(groupedDocuments)
              .sort(([a], [b]) => a.localeCompare(b))
              .map(([phase, docs]) => {
                const config = PHASE_CONFIG[phase] || PHASE_CONFIG.F0;
                return (
                  <div key={phase}>
                    {/* Phase header */}
                    <div className="mb-5">
                      <h2 className={`text-base font-medium ${config.color}`}>
                        {phase} — {docs[0]?.phaseName || config.label}
                      </h2>
                      <p className="text-navy-400 text-sm mt-0.5">
                        {docs.length} document{docs.length !== 1 ? 's' : ''}
                      </p>
                    </div>

                    {/* Document cards */}
                    <div className="grid gap-4">
                      {docs.map(doc => (
                        <div
                          key={doc.id}
                          className={`${config.bg} border border-navy-700 rounded-lg p-5 hover:border-navy-600 transition-colors group`}
                        >
                          <div className="flex items-start justify-between gap-5">
                            <div className="flex-1 min-w-0">
                              {/* Title + badges */}
                              <div className="flex items-center gap-2 mb-3 flex-wrap">
                                <h3 className="text-white text-lg font-semibold">
                                  {doc.title}
                                </h3>
                                <span className={`px-2 py-0.5 rounded text-xs font-medium ${CATEGORY_CONFIG[doc.category]?.color || 'text-navy-300 bg-navy-600'}`}>
                                  {CATEGORY_CONFIG[doc.category]?.label || doc.category}
                                </span>
                                {doc.adminOnly && (
                                  <span className="px-2 py-0.5 rounded text-xs font-medium text-red-400 bg-red-500/10">
                                    Admin Only
                                  </span>
                                )}
                              </div>

                              {/* Description */}
                              <p className="text-navy-200 text-sm leading-relaxed mb-4">
                                {doc.description}
                              </p>

                              {/* Trigger & Audience – sub-containers (dashboard/introducer style) */}
                              <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                                <div className="bg-navy-700/50 border border-navy-700 rounded-xl p-4">
                                  <div className="flex items-center gap-2 mb-2">
                                    <Zap className="w-3.5 h-3.5 text-amber-400" />
                                    <span className="text-xs text-navy-400 uppercase tracking-wider font-medium">Trigger</span>
                                  </div>
                                  <p className="text-sm text-white leading-snug">{doc.trigger}</p>
                                </div>
                                <div className="bg-navy-700/50 border border-navy-700 rounded-xl p-4">
                                  <div className="flex items-center gap-2 mb-2">
                                    <Users className="w-3.5 h-3.5 text-blue-400" />
                                    <span className="text-xs text-navy-400 uppercase tracking-wider font-medium">Audience</span>
                                  </div>
                                  <p className="text-sm text-white leading-snug">{doc.audience}</p>
                                </div>
                              </div>
                            </div>

                            {/* Download button */}
                            <button
                              onClick={() => handleDownload(doc)}
                              disabled={downloading === doc.id}
                              className="flex-shrink-0 px-3 py-2 bg-navy-700 hover:bg-navy-600 text-navy-200 hover:text-white rounded text-xs font-medium transition-colors disabled:opacity-50 group-hover:bg-emerald-500/20 group-hover:text-emerald-400"
                              title={`Download ${doc.filename}`}
                            >
                              {downloading === doc.id ? (
                                <span className="flex items-center gap-1">
                                  <span className="w-3 h-3 border border-current border-t-transparent rounded-full animate-spin" />
                                  ...
                                </span>
                              ) : (
                                <span className="flex items-center gap-1">
                                  <svg className="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 10v6m0 0l-3-3m3 3l3-3m2 8H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
                                  </svg>
                                  Download
                                </span>
                              )}
                            </button>
                          </div>
                        </div>
                      ))}
                    </div>
                  </div>
                );
              })}
          </div>
        )}

        {/* Summary footer */}
        <div className="mt-8 pt-6 border-t border-navy-700">
          <div className="flex flex-wrap gap-4 text-xs text-navy-500">
            <span>Total: {documents.length} documents</span>
            <span>Phases: {phases.length}</span>
            <span>Categories: {uniqueCategories.length}</span>
            {documents.some(d => d.adminOnly) && (
              <span className="text-red-400/60">
                Includes admin-only documents
              </span>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
