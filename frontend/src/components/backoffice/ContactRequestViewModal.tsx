/**
 * Modal that shows all contact request form data in a polished card layout.
 * Supports NDA viewing for both buyer (ContactRequest NDA) and introducer (User NDA) flows.
 * Focus trap, Escape to close, exit animation, optional IP lookup.
 *
 * Renders via createPortal into document.body to isolate from the list DOM and prevent
 * click-through (clicks on NDA buttons were previously reaching list items). NDA buttons
 * use handleNDAClick with stopPropagation/preventDefault for additional event isolation.
 */

import { useState, useEffect, useRef, useCallback } from 'react';
import { createPortal } from 'react-dom';
import { motion } from 'framer-motion';
import { X, ExternalLink, FileText, Building2, Clock, Globe, User, Hash, Tag, Mail, Briefcase } from 'lucide-react';
import { Badge } from '../common';
import { clientStatusVariant } from '../../utils/roleBadge';
import type { ContactRequest } from '../../types/backoffice';
import { formatDate } from '../../utils';

interface ContactRequestViewModalProps {
  request: ContactRequest | null;
  isOpen: boolean;
  onClose: () => void;
  onOpenNDA: (requestId: string) => Promise<void>;
  onOpenUserNDA?: (userId: string) => Promise<void>;
  onIpLookup?: (ip: string) => void;
  openNDALoading?: boolean;
  openUserNDALoading?: boolean;
  onAcceptNDA?: (requestId: string) => Promise<void>;
  acceptNDALoading?: boolean;
}

const FOCUSABLE_SELECTOR = 'button, [href], input, select, textarea, [tabindex]:not([tabindex="-1"])';

function SectionCard({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <div className="rounded-lg bg-navy-900/40 border border-navy-700 p-3">
      <div className="text-[10px] font-semibold uppercase tracking-widest text-navy-500 mb-2">
        {title}
      </div>
      <div className="space-y-1.5">
        {children}
      </div>
    </div>
  );
}

function DetailRow({
  icon: Icon,
  label,
  value,
  highlight = false,
  mono = false,
  truncate = false,
  children,
}: {
  icon?: React.ElementType;
  label: string;
  value?: string;
  highlight?: boolean;
  mono?: boolean;
  truncate?: boolean;
  children?: React.ReactNode;
}) {
  if (!value && !children) return null;
  return (
    <div className="flex items-center justify-between gap-3">
      <span className="text-xs text-navy-400 flex items-center gap-1.5 flex-shrink-0">
        {Icon && <Icon className="w-3 h-3" />}
        {label}
      </span>
      {children ?? (
        <span className={`text-xs text-right ${truncate ? 'truncate max-w-[200px]' : ''} ${
          highlight ? 'font-semibold text-white' : 'text-navy-300'
        } ${mono ? 'font-mono tabular-nums' : ''}`}>
          {value}
        </span>
      )}
    </div>
  );
}

export function ContactRequestViewModal({
  request,
  isOpen,
  onClose,
  onOpenNDA,
  onOpenUserNDA,
  onIpLookup,
  openNDALoading = false,
  openUserNDALoading = false,
  onAcceptNDA,
  acceptNDALoading = false,
}: ContactRequestViewModalProps) {
  const [exiting, setExiting] = useState(false);
  const [closingRequest, setClosingRequest] = useState<ContactRequest | null>(null);
  const [ndaViewed, setNdaViewed] = useState(false);
  const modalRef = useRef<HTMLDivElement>(null);
  const closeButtonRef = useRef<HTMLButtonElement>(null);

  const showingRequest = (isOpen && request) ? request : closingRequest;
  const isVisible = !!(isOpen && request) || (exiting && closingRequest);

  const handleClose = useCallback(() => {
    if (exiting) return;
    if (!request) {
      onClose();
      return;
    }
    setClosingRequest(request);
    setExiting(true);
  }, [exiting, request, onClose]);

  const handleAnimationComplete = useCallback(() => {
    if (exiting) {
      onClose();
      setExiting(false);
      setClosingRequest(null);
    }
  }, [exiting, onClose]);

  // Reset exiting when opening
  useEffect(() => {
    if (isOpen && request) setExiting(false);
  }, [isOpen, request]);

  // Reset NDA viewed tracking when modal opens with new request
  useEffect(() => {
    if (isOpen) setNdaViewed(false);
  }, [isOpen, request?.id]);

  // Escape to close
  useEffect(() => {
    if (!isVisible) return;
    const onKeyDown = (e: KeyboardEvent) => {
      if (e.key === 'Escape') {
        e.preventDefault();
        handleClose();
      }
    };
    document.addEventListener('keydown', onKeyDown);
    return () => document.removeEventListener('keydown', onKeyDown);
  }, [isVisible, handleClose]);

  // Focus close button on open
  useEffect(() => {
    if (!isVisible || !modalRef.current) return;
    closeButtonRef.current?.focus();
  }, [isVisible]);

  // Focus trap (Tab / Shift+Tab)
  useEffect(() => {
    if (!isVisible || !modalRef.current) return;
    const el = modalRef.current;
    const onKeyDown = (e: KeyboardEvent) => {
      if (e.key !== 'Tab') return;
      const focusable = Array.from(el.querySelectorAll<HTMLElement>(FOCUSABLE_SELECTOR));
      if (focusable.length === 0) return;
      const first = focusable[0];
      const last = focusable[focusable.length - 1];
      const active = document.activeElement as HTMLElement | null;
      if (e.shiftKey) {
        if (active === first) {
          e.preventDefault();
          last.focus();
        }
      } else {
        if (active === last) {
          e.preventDefault();
          first.focus();
        }
      }
    };
    el.addEventListener('keydown', onKeyDown);
    return () => el.removeEventListener('keydown', onKeyDown);
  }, [isVisible]);

  const handleNDAClick = useCallback(
    async (e: React.MouseEvent, fn: () => Promise<void>) => {
      e.preventDefault();
      e.stopPropagation();
      await fn();
      setNdaViewed(true);
    },
    []
  );

  if (!isVisible || !showingRequest) return null;

  const isIntroducer = showingRequest.requestFlow === 'introducer';
  const flowLabel = isIntroducer ? 'Introducer' : 'Buyer';
  const firstName = showingRequest.contactFirstName ?? showingRequest.contactName?.split(' ')[0];
  const lastName = showingRequest.contactLastName ?? showingRequest.contactName?.split(' ').slice(1).join(' ');
  const fullName = [firstName, lastName].filter(Boolean).join(' ') || '—';

  // NDA section logic
  const hasBuyerNDA = !!showingRequest.ndaFileName;
  const hasIntroducerNDA = isIntroducer && (
    (showingRequest.introducerNdaStatus === 'uploaded' && !!showingRequest.introducerUserId) ||
    showingRequest.introducerNdaStatus === 'attached'
  );
  const introducerNDAPending = isIntroducer && showingRequest.introducerNdaStatus === 'sent';
  const hasBuyerUploadedNDA = showingRequest.requestFlow === 'buyer' && !!showingRequest.buyerUserId && showingRequest.buyerNdaStatus === 'uploaded';
  const showNDASection = hasBuyerNDA || hasIntroducerNDA || introducerNDAPending || hasBuyerUploadedNDA || !!showingRequest.ndaAccepted;

  const modalContent = (
    <div
      className="fixed inset-0 bg-black/50 z-50 flex items-center justify-center p-4"
      onClick={handleClose}
      role="dialog"
      aria-modal="true"
      aria-labelledby="contact-request-view-title"
    >
      <motion.div
        ref={modalRef}
        initial={{ opacity: 0, scale: 0.95, y: 10 }}
        animate={exiting ? { opacity: 0, scale: 0.95, y: 10 } : { opacity: 1, scale: 1, y: 0 }}
        transition={{ duration: 0.15 }}
        onAnimationComplete={handleAnimationComplete}
        onClick={(e) => e.stopPropagation()}
        className="bg-navy-800 rounded-xl shadow-2xl border border-navy-700 w-full max-w-lg max-h-[85vh] overflow-hidden flex flex-col"
      >
        {/* ── Header ── */}
        <div className="flex items-start justify-between p-5 pb-4 border-b border-navy-700">
          <div className="flex items-start gap-3 min-w-0">
            <div className="p-2 rounded-lg flex-shrink-0 bg-emerald-900/20">
              <Building2 className="w-5 h-5 text-emerald-400" />
            </div>
            <div className="min-w-0">
              <h2 id="contact-request-view-title" className="text-base font-semibold text-white truncate">
                Contact Request
              </h2>
              <div className="flex items-center gap-2 mt-0.5">
                <Badge
                  variant={isIntroducer ? clientStatusVariant('PREINTRODUCER') : clientStatusVariant(showingRequest.userRole)}
                  className="text-[10px]"
                >
                  {flowLabel}
                </Badge>
                <span className="text-navy-600">·</span>
                <span className="text-xs text-navy-400">
                  {showingRequest.createdAt ? formatDate(showingRequest.createdAt) : '—'}
                </span>
              </div>
            </div>
          </div>
          <button
            ref={closeButtonRef}
            type="button"
            onClick={handleClose}
            className="p-1.5 hover:bg-navy-700 rounded-lg transition-colors flex-shrink-0 focus:outline-none focus:ring-2 focus:ring-emerald-500 focus:ring-offset-2 focus:ring-offset-navy-800"
            aria-label="Close"
          >
            <X className="w-4 h-4 text-navy-400" />
          </button>
        </div>

        {/* ── Scrollable Body ── */}
        <div className="flex-1 overflow-y-auto p-5 space-y-4">

          {/* ── Contact Card ── */}
          <SectionCard title="Contact">
            <DetailRow icon={User} label="Name" value={fullName} highlight />
            <DetailRow icon={Mail} label="Email" value={showingRequest.contactEmail} />
            <DetailRow icon={Briefcase} label="Position" value={showingRequest.position || undefined} />
            <DetailRow icon={Building2} label="Entity" value={showingRequest.entityName} highlight />
          </SectionCard>

          {/* ── Request Card ── */}
          <SectionCard title="Request">
            <DetailRow icon={Hash} label="ID" value={showingRequest.id} mono truncate />
            <DetailRow icon={Tag} label="User Role" value={showingRequest.userRole || '—'}>
              <Badge
                variant={clientStatusVariant(showingRequest.userRole)}
                className="text-[10px]"
              >
                {showingRequest.userRole || '—'}
              </Badge>
            </DetailRow>
            <DetailRow label="Request Flow" value={flowLabel} />
            {showingRequest.referralCodeUsed && (
              <DetailRow label="Referral Code" value={showingRequest.referralCodeUsed} mono />
            )}
          </SectionCard>

          {/* ── Referral Card ── */}
          {showingRequest.introducerName && (
            <SectionCard title="Referral">
              <DetailRow icon={User} label="Introduced by" value={showingRequest.introducerName} />
            </SectionCard>
          )}

          {/* ── NDA Document Card ── */}
          {showNDASection && (
            <SectionCard title="NDA Document">
              {/* Buyer NDA (from ContactRequest) */}
              {hasBuyerNDA && (
                <button
                  type="button"
                  onClick={(e) => handleNDAClick(e, () => onOpenNDA(showingRequest.id))}
                  disabled={openNDALoading}
                  className="w-full flex items-center gap-2.5 px-3 py-2 rounded-lg border border-navy-600 bg-navy-900/50 text-navy-200 hover:bg-navy-700/50 transition-colors text-sm font-medium focus:outline-none focus:ring-2 focus:ring-emerald-500 focus:ring-offset-2 focus:ring-offset-navy-800 disabled:opacity-50 disabled:cursor-not-allowed"
                  aria-label={`Open NDA ${showingRequest.ndaFileName}`}
                >
                  <FileText className="w-4 h-4 shrink-0 text-navy-400" />
                  <span className="flex-1 text-left truncate text-xs">
                    {openNDALoading ? 'Opening…' : (showingRequest.ndaFileName ?? 'View NDA')}
                  </span>
                  <ExternalLink className="w-3.5 h-3.5 shrink-0 text-navy-500" />
                </button>
              )}

              {/* Introducer signed NDA (from User model) — only when user exists */}
              {hasIntroducerNDA && onOpenUserNDA && showingRequest.introducerUserId && (
                <button
                  type="button"
                  onClick={(e) => handleNDAClick(e, () => onOpenUserNDA!(showingRequest.introducerUserId!))}
                  disabled={openUserNDALoading}
                  className="w-full flex items-center gap-2.5 px-3 py-2 rounded-lg border border-emerald-600/40 bg-emerald-900/10 text-emerald-300 hover:bg-emerald-900/20 transition-colors text-sm font-medium focus:outline-none focus:ring-2 focus:ring-emerald-500 focus:ring-offset-2 focus:ring-offset-navy-800 disabled:opacity-50 disabled:cursor-not-allowed"
                  aria-label="View Signed NDA"
                >
                  <FileText className="w-4 h-4 shrink-0" />
                  <span className="flex-1 text-left truncate text-xs">
                    {openUserNDALoading ? 'Opening…' : 'View Signed NDA'}
                  </span>
                  <ExternalLink className="w-3.5 h-3.5 shrink-0 text-emerald-500/60" />
                </button>
              )}

              {/* Attached NDA (uploaded with form, no user yet) — use contact request NDA viewer */}
              {hasIntroducerNDA && !showingRequest.introducerUserId && (
                <button
                  type="button"
                  onClick={(e) => handleNDAClick(e, () => onOpenNDA(showingRequest.id))}
                  disabled={openNDALoading}
                  className="w-full flex items-center gap-2.5 px-3 py-2 rounded-lg border border-emerald-600/40 bg-emerald-900/10 text-emerald-300 hover:bg-emerald-900/20 transition-colors text-sm font-medium focus:outline-none focus:ring-2 focus:ring-emerald-500 focus:ring-offset-2 focus:ring-offset-navy-800 disabled:opacity-50 disabled:cursor-not-allowed"
                  aria-label="View Attached NDA"
                >
                  <FileText className="w-4 h-4 shrink-0" />
                  <span className="flex-1 text-left truncate text-xs">
                    {openNDALoading ? 'Opening…' : 'View Attached NDA'}
                  </span>
                  <ExternalLink className="w-3.5 h-3.5 shrink-0 text-emerald-500/60" />
                </button>
              )}

              {/* Introducer NDA sent but not yet uploaded */}
              {introducerNDAPending && (
                <div className="flex items-center gap-2 px-3 py-2 rounded-lg border border-amber-600/30 bg-amber-900/10 text-xs text-amber-400">
                  <FileText className="w-4 h-4 shrink-0" />
                  NDA sent — awaiting upload from introducer
                </div>
              )}

              {/* Buyer uploaded NDA (referred buyer flow) */}
              {showingRequest.requestFlow === 'buyer' && showingRequest.buyerUserId && showingRequest.buyerNdaStatus === 'uploaded' && onOpenUserNDA && (
                <button
                  type="button"
                  onClick={(e) => handleNDAClick(e, () => onOpenUserNDA(showingRequest.buyerUserId!))}
                  disabled={openUserNDALoading}
                  className="flex items-center gap-2 px-3 py-1.5 rounded-lg bg-emerald-600/20 text-emerald-300 hover:bg-emerald-600/30 border border-emerald-500/30 transition-colors text-sm"
                >
                  <FileText size={14} />
                  <span>{openUserNDALoading ? 'Opening...' : 'View Uploaded NDA'}</span>
                  <ExternalLink size={12} className="ml-auto opacity-60" />
                </button>
              )}

              {/* Accept NDA button — shown after admin views NDA, only for NDA role, only if not yet accepted */}
              {showingRequest.userRole === 'NDA' && !showingRequest.ndaAccepted && ndaViewed && onAcceptNDA && (
                <button
                  type="button"
                  onClick={(e) => { e.preventDefault(); e.stopPropagation(); onAcceptNDA(showingRequest.id); }}
                  disabled={acceptNDALoading}
                  className="mt-2 w-full flex items-center justify-center gap-2 px-3 py-2 rounded-lg bg-emerald-600/20 text-emerald-400 hover:bg-emerald-600/30 border border-emerald-500/30 transition-colors text-sm font-medium disabled:opacity-50"
                >
                  {acceptNDALoading ? 'Accepting...' : 'Accept NDA'}
                </button>
              )}

              {/* NDA accepted badge */}
              {showingRequest.ndaAccepted && (
                <div className="mt-2 flex items-center gap-1.5 text-emerald-400 text-xs">
                  <svg xmlns="http://www.w3.org/2000/svg" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M22 11.08V12a10 10 0 1 1-5.93-9.14"/><polyline points="22 4 12 14.01 9 11.01"/></svg>
                  <span>NDA Accepted</span>
                </div>
              )}
            </SectionCard>
          )}
        </div>

        {/* ── Metadata Footer ── */}
        <div className="border-t border-navy-700 px-5 py-3 space-y-1.5">
          <div className="flex items-center justify-between gap-3">
            <span className="text-[11px] text-navy-500 flex items-center gap-1.5">
              <Clock className="w-3 h-3" />
              Submitted
            </span>
            <span className="text-[11px] text-navy-400">
              {showingRequest.createdAt ? formatDate(showingRequest.createdAt) : '—'}
            </span>
          </div>

          {showingRequest.submitterIp && (
            <div className="flex items-center justify-between gap-3">
              <span className="text-[11px] text-navy-500 flex items-center gap-1.5">
                <Globe className="w-3 h-3" />
                IP Address
              </span>
              <span className="text-[11px] text-navy-400 flex items-center gap-1.5">
                {showingRequest.submitterIp}
                {onIpLookup && (
                  <button
                    type="button"
                    onClick={() => onIpLookup(showingRequest.submitterIp!)}
                    className="text-[10px] font-medium text-emerald-400 hover:underline focus:outline-none"
                    aria-label={`Lookup IP ${showingRequest.submitterIp}`}
                  >
                    Lookup
                  </button>
                )}
              </span>
            </div>
          )}

          {showingRequest.notes && (
            <div className="pt-1">
              <span className="text-[11px] text-navy-500">Notes</span>
              <p className="text-[11px] text-navy-400 mt-0.5">{showingRequest.notes}</p>
            </div>
          )}
        </div>
      </motion.div>
    </div>
  );

  return createPortal(modalContent, document.body);
}
