import { useState, useEffect, useCallback } from 'react';
import { Link, useLocation } from 'react-router-dom';
import {
  FileText,
  Users,
  RefreshCw,
  Wifi,
  WifiOff,
  Banknote,
  Shield,
  CheckCircle,
  XCircle,
  Timer,
  Unlink,
  Trash2,
} from 'lucide-react';
import { Button, Card, Badge, AlertBanner } from '../components/common';
import { BackofficeLayout } from '../components/layout';
import {
  ContactRequestsTab,
  PendingDepositsTab,
  DocumentViewerModal,
  KYCReviewTab,
  IPLookupModal,
} from '../components/backoffice';
import { adminApi, backofficeApi } from '../services/api';
import { cn } from '../utils';
import { getApiErrorMessage } from '../utils/errors';
import { useBackofficeRealtime } from '../hooks/useBackofficeRealtime';
import { isPendingContactRequest } from '../utils/contactRequest';
import { logger } from '../utils/logger';
import type {
  ContactRequest,
  PendingUserResponse,
  KYCUser,
  KYCDocument,
  PendingDeposit,
  DocumentViewerState,
} from '../types/backoffice';
import type { Deposit, AdminSettlementBatch } from '../types';

interface IPLookupResult {
  ip: string;
  country: string;
  country_code: string;
  region: string;
  city: string;
  zip: string;
  lat: number;
  lon: number;
  timezone: string;
  isp: string;
  org: string;
  as: string;
}

interface KycDocResponse {
  id: string;
  status: string;
  createdAt: string;
  userId: string;
  documentType: string;
  fileName: string;
}

interface PendingDepositResponse {
  id: string;
  entityId?: string;
  entityName?: string;
  userEmail?: string;
  userRole: string;
  reportedAmount?: number | null;
  reportedCurrency?: string | null;
  wireReference?: string | null;
  bankReference?: string | null;
  status: string;
  reportedAt?: string | null;
  notes?: string | null;
  createdAt?: string;
}

type OnboardingSubpage = 'requests' | 'introducer' | 'kyc' | 'deposits' | 'aml' | 'settlements';

const ONBOARDING_SUBPAGES: { path: OnboardingSubpage; label: string; icon: React.ElementType }[] = [
  { path: 'requests', label: 'Contact Requests', icon: Users },
  { path: 'introducer', label: 'Introducer', icon: Users },
  { path: 'kyc', label: 'KYC Review', icon: FileText },
  { path: 'deposits', label: 'Deposits', icon: Banknote },
  { path: 'aml', label: 'AML', icon: Shield },
  { path: 'settlements', label: 'Settlements', icon: Timer },
];

function getOnboardingSubpage(pathname: string): OnboardingSubpage {
  if (pathname.endsWith('/kyc') || pathname.includes('/onboarding/kyc')) return 'kyc';
  if (pathname.endsWith('/introducer') || pathname.includes('/onboarding/introducer')) return 'introducer';
  if (pathname.endsWith('/deposits') || pathname.includes('/onboarding/deposits')) return 'deposits';
  if (pathname.endsWith('/aml') || pathname.includes('/onboarding/aml')) return 'aml';
  if (pathname.endsWith('/settlements') || pathname.includes('/onboarding/settlements')) return 'settlements';
  return 'requests';
}

export function BackofficeOnboardingPage() {
  const { pathname } = useLocation();
  const activeSubpage = getOnboardingSubpage(pathname);

  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const {
    contactRequests: realtimeContactRequests,
    connectionStatus,
    refresh: refreshContactRequests,
    removeContactRequest,
  } = useBackofficeRealtime();

  const allMapped: ContactRequest[] = realtimeContactRequests.map(r => ({
    id: r.id,
    entityName: r.entityName,
    contactEmail: r.contactEmail,
    contactName: r.contactName,
    contactFirstName: r.contactFirstName,
    contactLastName: r.contactLastName,
    position: r.position || '',
    ndaFileName: r.ndaFileName,
    submitterIp: r.submitterIp,
    userRole: ('userRole' in r ? r.userRole : (r as { status?: string }).status) ?? 'new',
    requestFlow: (r as { requestFlow?: string }).requestFlow ?? 'buyer',
    referredByUserId: (r as { referredByUserId?: string }).referredByUserId,
    referralCodeUsed: (r as { referralCodeUsed?: string }).referralCodeUsed,
    introducerNdaStatus: (r as { introducerNdaStatus?: 'not_sent' | 'sent' | 'uploaded' | 'attached' }).introducerNdaStatus,
    introducerUserId: (r as { introducerUserId?: string }).introducerUserId,
    buyerNdaStatus: (r as { buyerNdaStatus?: 'not_sent' | 'sent' | 'uploaded' | 'attached' | 'no_nda' }).buyerNdaStatus,
    buyerUserId: (r as { buyerUserId?: string }).buyerUserId,
    ndaAccepted: (r as { ndaAccepted?: boolean }).ndaAccepted,
    notes: r.notes,
    createdAt: r.createdAt,
  }));
  // Only show pending requests (NDA, new); KYC and REJECTED disappear immediately after approval
  const contactRequests: ContactRequest[] = allMapped.filter(r =>
    isPendingContactRequest(r.userRole)
  );
  const introducerRequests: ContactRequest[] = contactRequests.filter(r => r.requestFlow === 'introducer');
  const buyerRequests: ContactRequest[] = contactRequests.filter(r => r.requestFlow !== 'introducer');

  const [kycUsers, setKycUsers] = useState<KYCUser[]>([]);
  const [kycDocuments, setKycDocuments] = useState<KYCDocument[]>([]);
  const [showDocumentViewer, setShowDocumentViewer] = useState<DocumentViewerState | null>(null);
  const [documentContentUrl, setDocumentContentUrl] = useState<string | null>(null);
  const [documentLoading, setDocumentLoading] = useState(false);
  const [documentError, setDocumentError] = useState<string | null>(null);
  const [ipLookupData, setIpLookupData] = useState<IPLookupResult | null>(null);
  const [ipLookupLoading, setIpLookupLoading] = useState(false);
  const [showIpModal, setShowIpModal] = useState(false);
  const [actionLoading, setActionLoading] = useState<string | null>(null);
  const [reconcileSuccess, setReconcileSuccess] = useState<string | null>(null);
  const [pendingDeposits, setPendingDeposits] = useState<PendingDeposit[]>([]);
  const [amlDeposits, setAmlDeposits] = useState<Deposit[]>([]);
  const [settlementBatches, setSettlementBatches] = useState<AdminSettlementBatch[]>([]);
  // Real-time settlement count — kept in sync via WS regardless of active subpage
  const [pendingSettlementsCount, setPendingSettlementsCount] = useState<number>(0);
  // AML batch selection
  const [amlSelectedIds, setAmlSelectedIds] = useState<Set<string>>(new Set());
  const [amlBatchLoading, setAmlBatchLoading] = useState<'reject' | null>(null);

  const loadData = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      if (activeSubpage === 'kyc') {
        const [users, docs] = await Promise.all([
          backofficeApi.getPendingUsers(),
          backofficeApi.getKYCDocuments(),
        ]);
        setKycUsers(users.map((u: PendingUserResponse & { firstName?: string; lastName?: string; entityName?: string; documentsCount?: number; createdAt?: string }): KYCUser => ({
          id: u.id,
          email: u.email,
          firstName: u.firstName ?? '',
          lastName: u.lastName ?? '',
          entityName: u.entityName ?? '',
          documentsCount: u.documentsCount ?? 0,
          createdAt: u.createdAt ?? new Date().toISOString(),
        })));
        // API response is camelCase; normalize so getUserDocuments and KYCReviewPanel work
        setKycDocuments((docs as KycDocResponse[]).map((d) => ({
          ...d,
          id: d.id,
          status: d.status,
          createdAt: d.createdAt,
          userId: d.userId,
          documentType: d.documentType,
          fileName: d.fileName,
        })));
      } else if (activeSubpage === 'deposits') {
        const pendingRes = await backofficeApi.getPendingDeposits();
        setPendingDeposits((pendingRes as PendingDepositResponse[]).map((d): PendingDeposit => ({
          id: d.id,
          entityId: d.entityId ?? '',
          entityName: d.entityName ?? '',
          userEmail: d.userEmail ?? '',
          userRole: d.userRole,
          reportedAmount: d.reportedAmount ?? null,
          reportedCurrency: d.reportedCurrency ?? null,
          wireReference: d.wireReference ?? null,
          bankReference: d.bankReference ?? null,
          status: d.status,
          reportedAt: d.reportedAt ?? null,
          notes: d.notes ?? null,
          createdAt: d.createdAt ?? '',
        })));
      } else if (activeSubpage === 'aml') {
        const onHoldRes = await backofficeApi.getOnHoldDeposits({ include_expired: true });
        setAmlDeposits(onHoldRes.deposits || []);
      } else if (activeSubpage === 'settlements') {
        const res = await adminApi.getAdminPendingSettlements();
        setSettlementBatches(res.data || []);
        // Keep real-time count in sync with full list
        setPendingSettlementsCount(res.count ?? res.data?.length ?? 0);
      }
    } catch (err: unknown) {
      logger.error('Failed to load data', err);
      setError(getApiErrorMessage(err));
    } finally {
      setLoading(false);
    }
  }, [activeSubpage]);

  useEffect(() => {
    if (activeSubpage !== 'requests') {
      loadData();
    } else {
      setLoading(realtimeContactRequests.length === 0 && connectionStatus === 'connecting');
    }
  }, [activeSubpage, realtimeContactRequests.length, connectionStatus, loadData]);

  // Fetch settlement count on mount (independent of active subpage — badge must always be current)
  useEffect(() => {
    adminApi.getAdminPendingSettlements().then(res => {
      setPendingSettlementsCount(res.count ?? res.data?.length ?? 0);
    }).catch(() => {/* ignore — badge stays at 0 */});
  }, []);

  // Real-time settlement badge: listen for WS events dispatched by useBackofficeRealtime
  useEffect(() => {
    const handleSettlementChanged = () => {
      // Re-fetch count so badge is always accurate
      adminApi.getAdminPendingSettlements().then(res => {
        setPendingSettlementsCount(res.count ?? res.data?.length ?? 0);
        // If currently viewing settlements tab, also refresh the full list
        if (activeSubpage === 'settlements') {
          setSettlementBatches(res.data || []);
        }
      }).catch(() => {});
    };

    window.addEventListener('nihao:settlementChanged', handleSettlementChanged);
    return () => window.removeEventListener('nihao:settlementChanged', handleSettlementChanged);
  }, [activeSubpage]);

  const handleRefresh = () => {
    if (activeSubpage === 'requests' || activeSubpage === 'introducer') {
      refreshContactRequests();
    } else {
      loadData();
    }
  };

  const handleReconcileIntroducerOrphans = async () => {
    setActionLoading('reconcile-introducer-orphans');
    setReconcileSuccess(null);
    setError(null);
    try {
      const { deleted } = await adminApi.reconcileIntroducerOrphanContactRequests();
      refreshContactRequests();
      setReconcileSuccess(
        deleted === 0
          ? 'No orphan introducer contact requests found.'
          : `Removed ${deleted} orphan introducer contact request${deleted === 1 ? '' : 's'}.`
      );
    } catch (err: unknown) {
      logger.error('Failed to reconcile introducer orphans', err);
      setError(getApiErrorMessage(err));
    } finally {
      setActionLoading(null);
    }
  };

  const handleOpenNDA = async (requestId: string) => {
    setActionLoading(`open-${requestId}`);
    try {
      const request = contactRequests.find(r => r.id === requestId);
      if (request?.ndaFileName) {
        await adminApi.openNDAInBrowser(requestId, request.ndaFileName);
      }
    } catch (err) {
      logger.error('Failed to open NDA', err);
      setError(
        err instanceof Error && err.message === 'POPUP_BLOCKED'
          ? 'Allow pop-ups for this site and try again.'
          : 'Failed to open NDA file'
      );
    } finally {
      setActionLoading(null);
    }
  };

  const handleOpenUserNDA = async (userId: string) => {
    setActionLoading(`open-user-nda-${userId}`);
    try {
      await adminApi.openUserNDAInBrowser(userId);
    } catch (err) {
      logger.error('Failed to open user NDA', err);
      setError(
        err instanceof Error && err.message === 'POPUP_BLOCKED'
          ? 'Allow pop-ups for this site and try again.'
          : 'Failed to open NDA file'
      );
    } finally {
      setActionLoading(null);
    }
  };

  const handleIpLookup = async (ip: string) => {
    if (!ip || ip === 'null' || ip === 'None') {
      setError('Invalid IP address');
      return;
    }
    setIpLookupLoading(true);
    setShowIpModal(true);
    try {
      const data = await adminApi.lookupIP(ip);
      setIpLookupData(data);
    } catch (err: unknown) {
      logger.error('Failed to lookup IP', err);
      setIpLookupData(null);
      setError(getApiErrorMessage(err));
    } finally {
      setIpLookupLoading(false);
    }
  };

  const handleRejectRequest = async (requestId: string) => {
    setActionLoading(`reject-${requestId}`);
    try {
      await adminApi.updateContactRequest(requestId, { userRole: 'REJECTED' });
    } catch (err) {
      logger.error('Failed to reject request', err);
    } finally {
      setActionLoading(null);
    }
  };

  const handleApproveRequest = async () => {
    refreshContactRequests();
  };

  const handleApproveIntroducer = async (userId: string) => {
    setActionLoading(`approve-introducer-${userId}`);
    try {
      await adminApi.approveIntroducerNDA(userId);
      refreshContactRequests();
    } catch (err: unknown) {
      logger.error('Failed to approve introducer', err);
      setError(getApiErrorMessage(err));
    } finally {
      setActionLoading(null);
    }
  };

  const handleSendBuyerNDA = async (requestId: string) => {
    setActionLoading(requestId);
    try {
      await adminApi.sendBuyerNDA(requestId);
      await refreshContactRequests();
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : 'Failed to send NDA';
      console.error('Failed to send buyer NDA:', msg);
    } finally {
      setActionLoading(null);
    }
  };

  const handleAcceptNDA = async (requestId: string) => {
    setActionLoading(requestId);
    try {
      await adminApi.acceptNDA(requestId);
      await refreshContactRequests();
    } catch (err: unknown) {
      setError(getApiErrorMessage(err));
    } finally {
      setActionLoading(null);
    }
  };

  const handleApproveBuyerNDA = async (userId: string) => {
    setActionLoading(userId);
    try {
      await adminApi.approveIntroducerNDA(userId);
      await refreshContactRequests();
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : 'Failed to approve NDA';
      console.error('Failed to approve buyer NDA:', msg);
    } finally {
      setActionLoading(null);
    }
  };

  const handleDeleteRequest = async (requestId: string) => {
    setActionLoading(`delete-${requestId}`);
    try {
      await adminApi.deleteContactRequest(requestId);
      removeContactRequest(requestId);
    } catch (err: unknown) {
      logger.error('Failed to delete request', err);
      setError(getApiErrorMessage(err));
    } finally {
      setActionLoading(null);
    }
  };

  const handleConfirmDeposit = async (depositId: string, amount: number, currency: string, notes?: string) => {
    setActionLoading(`confirm-${depositId}`);
    try {
      await backofficeApi.confirmDeposit(depositId, amount, currency, notes);
      setPendingDeposits(prev => prev.filter(d => d.id !== depositId));
    } catch (err: unknown) {
      logger.error('Failed to confirm deposit', err);
      setError(getApiErrorMessage(err));
    } finally {
      setActionLoading(null);
    }
  };

  const handleRejectDeposit = async (depositId: string) => {
    setActionLoading(`reject-${depositId}`);
    try {
      await backofficeApi.rejectDeposit(depositId);
      setPendingDeposits(prev => prev.filter(d => d.id !== depositId));
    } catch (err: unknown) {
      logger.error('Failed to reject deposit', err);
      setError(getApiErrorMessage(err));
    } finally {
      setActionLoading(null);
    }
  };

  // AML Tab handlers
  const handleClearAML = async (depositId: string) => {
    setActionLoading(`aml-clear-${depositId}`);
    try {
      await backofficeApi.clearDeposit(depositId, { forceClear: true, adminNotes: 'AML cleared by admin' });
      setAmlDeposits(prev => prev.filter(d => d.id !== depositId));
    } catch (err: unknown) {
      logger.error('Failed to clear AML deposit', err);
      setError(getApiErrorMessage(err));
    } finally {
      setActionLoading(null);
    }
  };

  const handleRejectAML = async (depositId: string) => {
    setActionLoading(`aml-reject-${depositId}`);
    try {
      await backofficeApi.rejectDeposit(depositId);
      setAmlDeposits(prev => prev.filter(d => d.id !== depositId));
    } catch (err: unknown) {
      logger.error('Failed to reject AML deposit', err);
      setError(getApiErrorMessage(err));
    } finally {
      setActionLoading(null);
    }
  };

  const handleBatchRejectAML = async () => {
    setAmlBatchLoading('reject');
    const ids = Array.from(amlSelectedIds);
    for (const id of ids) {
      await backofficeApi.rejectDeposit(id).catch(() => {});
    }
    setAmlDeposits(prev => prev.filter(d => !amlSelectedIds.has(d.id)));
    setAmlSelectedIds(new Set());
    setAmlBatchLoading(null);
  };

  const loadDocumentContent = async (documentId: string) => {
    setDocumentLoading(true);
    setDocumentError(null);
    setDocumentContentUrl(null);
    try {
      const blob = await backofficeApi.getDocumentContent(documentId);
      const url = URL.createObjectURL(blob);
      setDocumentContentUrl(url);
    } catch (err: unknown) {
      logger.error('Failed to load document', err);
      setDocumentError(getApiErrorMessage(err));
    } finally {
      setDocumentLoading(false);
    }
  };

  const handleOpenDocumentViewer = (doc: KYCDocument) => {
    setShowDocumentViewer({
      id: doc.id,
      fileName: doc.fileName,
      type: doc.documentType,
      mimeType: doc.mimeType,
    });
    loadDocumentContent(doc.id);
  };

  const handleCloseDocumentViewer = () => {
    if (documentContentUrl) URL.revokeObjectURL(documentContentUrl);
    setShowDocumentViewer(null);
    setDocumentContentUrl(null);
    setDocumentError(null);
  };

  const handleDownloadDocument = () => {
    if (!showDocumentViewer || !documentContentUrl) return;
    const link = document.createElement('a');
    link.href = documentContentUrl;
    link.download = showDocumentViewer.fileName;
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
  };

  const handleApproveKYC = async (userId: string) => {
    setActionLoading(userId);
    try {
      await backofficeApi.approveUser(userId);
      setKycUsers(prev => prev.filter(u => u.id !== userId));
    } catch (err) {
      logger.error('Failed to approve user', err);
    } finally {
      setActionLoading(null);
    }
  };

  const handleRejectKYC = async (userId: string) => {
    setActionLoading(userId);
    try {
      await backofficeApi.rejectUser(userId, 'KYC verification failed');
      setKycUsers(prev => prev.filter(u => u.id !== userId));
    } catch (err) {
      logger.error('Failed to reject user', err);
    } finally {
      setActionLoading(null);
    }
  };

  const handleReviewDocument = async (docId: string, status: 'approved' | 'rejected', notes?: string) => {
    setActionLoading(docId);
    try {
      await backofficeApi.reviewDocument(docId, status, notes);
      setKycDocuments(prev =>
        prev.map(d => (d.id === docId ? { ...d, status } : d))
      );
    } catch (err) {
      logger.error('Failed to review document', err);
    } finally {
      setActionLoading(null);
    }
  };

  const handleSettleNow = async (batchId: string) => {
    setActionLoading(`settle-${batchId}`);
    try {
      await adminApi.settleSettlementBatch(batchId);
      setSettlementBatches(prev => prev.filter(b => b.id !== batchId));
    } catch (err: unknown) {
      logger.error('Failed to settle batch', err);
      setError(getApiErrorMessage(err));
    } finally {
      setActionLoading(null);
    }
  };

  const getUserDocuments = (userId: string) =>
    kycDocuments.filter(d => d.userId === userId);

  const subSubHeaderLeft = (
    <nav className="flex items-center gap-2" aria-label="Onboarding subpages">
      {ONBOARDING_SUBPAGES.map(({ path, label, icon: Icon }) => {
        const to = `/backoffice/onboarding/${path}`;
        const isActive = activeSubpage === path;
        const count = path === 'requests' ? buyerRequests.length : path === 'introducer' ? introducerRequests.length : path === 'kyc' ? kycUsers.length : path === 'aml' ? amlDeposits.length : path === 'settlements' ? pendingSettlementsCount : pendingDeposits.length;
        return (
          <Link
            key={path}
            to={to}
            aria-label={label}
            aria-current={isActive ? 'page' : undefined}
            title={label}
            className={cn(
              'group subsubheader-nav-btn flex items-center gap-2',
              isActive ? 'subsubheader-nav-btn-active' : 'subsubheader-nav-btn-inactive'
            )}
          >
            <Icon className="w-4 h-4 flex-shrink-0" aria-hidden="true" />
            <span className="whitespace-nowrap">{label}</span>
            {count > 0 && (
              <span className="subsubheader-nav-badge" aria-label={`${count} items`}>
                {count}
              </span>
            )}
          </Link>
        );
      })}
    </nav>
  );

  const subSubHeaderRight = (
    <div className="flex items-center gap-2">
      {activeSubpage === 'requests' && (
        <div
          className={cn(
            'flex items-center gap-2 px-3 py-1.5 rounded-xl text-xs font-medium',
            connectionStatus === 'connected' && 'bg-navy-700 text-navy-300',
            connectionStatus === 'connecting' && 'bg-navy-700 text-navy-400',
            connectionStatus === 'disconnected' && 'bg-navy-700 text-navy-400',
            connectionStatus === 'error' && 'bg-red-500/20 text-red-400'
          )}
        >
          {connectionStatus === 'connected' ? (
            <><Wifi className="w-3 h-3" /> Live</>
          ) : connectionStatus === 'connecting' ? (
            <><RefreshCw className="w-3 h-3 animate-spin" /> Connecting...</>
          ) : connectionStatus === 'error' ? (
            <><WifiOff className="w-3 h-3" /> Error</>
          ) : (
            <><WifiOff className="w-3 h-3" /> Offline</>
          )}
        </div>
      )}
      {activeSubpage === 'introducer' && (
        <Button
          variant="ghost"
          size="sm"
          onClick={handleReconcileIntroducerOrphans}
          loading={actionLoading === 'reconcile-introducer-orphans'}
          disabled={!!actionLoading && actionLoading !== 'reconcile-introducer-orphans'}
          icon={<Unlink className="w-4 h-4" />}
          title="Remove introducer contact requests when no PREINTRODUCER/INTRODUCER user exists for that email (e.g. after manual user deletion)."
        >
          Reconcile orphans
        </Button>
      )}
      <Button
        variant="ghost"
        size="sm"
        onClick={handleRefresh}
        icon={<RefreshCw className={cn('w-4 h-4', loading && 'animate-spin')} />}
      >
        Refresh
      </Button>
    </div>
  );

  return (
    <BackofficeLayout
      subSubHeaderLeft={subSubHeaderLeft}
      subSubHeader={subSubHeaderRight}
    >
      {reconcileSuccess && (
        <AlertBanner
          variant="success"
          message={reconcileSuccess}
          onDismiss={() => setReconcileSuccess(null)}
          className="mb-4"
        />
      )}

      {error && (
        <AlertBanner
          variant="error"
          message={error}
          onDismiss={() => setError(null)}
          className="mb-4"
        />
      )}

      {activeSubpage === 'requests' && (
        <ContactRequestsTab
          contactRequests={buyerRequests}
          loading={loading}
          connectionStatus={connectionStatus}
          onRefresh={handleRefresh}
          onApprove={handleApproveRequest}
          onReject={handleRejectRequest}
          onDelete={handleDeleteRequest}
          onOpenNDA={handleOpenNDA}
          onOpenUserNDA={handleOpenUserNDA}
          onIpLookup={handleIpLookup}
          onSendBuyerNDA={handleSendBuyerNDA}
          onAcceptNDA={handleAcceptNDA}
          onApproveBuyerNDA={handleApproveBuyerNDA}
          actionLoading={actionLoading}
        />
      )}

      {activeSubpage === 'introducer' && (
        <ContactRequestsTab
          contactRequests={introducerRequests}
          loading={loading}
          connectionStatus={connectionStatus}
          onRefresh={handleRefresh}
          onApprove={handleApproveRequest}
          onReject={handleRejectRequest}
          onDelete={handleDeleteRequest}
          onOpenNDA={handleOpenNDA}
          onOpenUserNDA={handleOpenUserNDA}
          onIpLookup={handleIpLookup}
          onApproveIntroducer={handleApproveIntroducer}
          actionLoading={actionLoading}
        />
      )}

      {activeSubpage === 'kyc' && (
        <KYCReviewTab
          kycUsers={kycUsers}
          kycDocuments={kycDocuments}
          loading={loading}
          actionLoading={actionLoading}
          onApproveKYC={handleApproveKYC}
          onRejectKYC={handleRejectKYC}
          onReviewDocument={handleReviewDocument}
          onOpenDocumentViewer={handleOpenDocumentViewer}
          getUserDocuments={getUserDocuments}
          setActionLoading={setActionLoading}
        />
      )}

      {activeSubpage === 'deposits' && (
        <PendingDepositsTab
          pendingDeposits={pendingDeposits}
          loading={loading}
          onConfirm={handleConfirmDeposit}
          onReject={handleRejectDeposit}
          actionLoading={actionLoading}
        />
      )}

      {activeSubpage === 'aml' && (
        <Card>
          <div className="flex items-center gap-2 mb-6">
            <Shield className="w-5 h-5 text-amber-500" />
            <h2 className="text-lg font-semibold text-white">
              AML Review Queue
            </h2>
            <Badge variant="warning" className="ml-2">
              {amlDeposits.length} pending
            </Badge>
          </div>

          {/* Batch action toolbar */}
          {!loading && amlDeposits.length > 0 && (() => {
            const allAmlIds = amlDeposits.map(d => d.id);
            const allAmlSelected = allAmlIds.every(id => amlSelectedIds.has(id));
            const someAmlSelected = amlSelectedIds.size > 0;
            return (
              <div className="flex items-center gap-3 mb-4 pb-4 border-b border-navy-700">
                <label className="flex items-center gap-2 cursor-pointer select-none">
                  <input
                    type="checkbox"
                    checked={allAmlSelected}
                    ref={el => { if (el) el.indeterminate = someAmlSelected && !allAmlSelected; }}
                    onChange={() => setAmlSelectedIds(allAmlSelected ? new Set() : new Set(allAmlIds))}
                    className="w-4 h-4 rounded border-navy-600 bg-navy-800 accent-emerald-500 cursor-pointer"
                    aria-label="Select all AML deposits"
                  />
                  <span className="text-xs text-navy-400">
                    {someAmlSelected ? `${amlSelectedIds.size} selected` : 'Select all'}
                  </span>
                </label>
                {someAmlSelected && (
                  <Button
                    variant="ghost"
                    size="sm"
                    onClick={handleBatchRejectAML}
                    loading={amlBatchLoading === 'reject'}
                    disabled={amlBatchLoading !== null}
                    className="ml-auto text-red-500 hover:text-red-400 hover:bg-red-500/10"
                  >
                    <Trash2 className="w-3.5 h-3.5 mr-1" />
                    Reject {amlSelectedIds.size}
                  </Button>
                )}
              </div>
            );
          })()}

          {loading ? (
            <div className="space-y-4">
              {[...Array(3)].map((_, i) => (
                <div key={i} className="animate-pulse p-4 bg-navy-700 rounded-xl">
                  <div className="h-4 bg-navy-600 rounded w-1/3 mb-2" />
                  <div className="h-3 bg-navy-600 rounded w-1/2" />
                </div>
              ))}
            </div>
          ) : amlDeposits.length === 0 ? (
            <div className="text-center py-12 text-navy-400">
              <Shield className="w-12 h-12 mx-auto mb-4 opacity-50" />
              <p>No deposits pending AML review</p>
            </div>
          ) : (
            <div className="space-y-4">
              {amlDeposits.map((deposit) => {
                const holdExpiresAt = deposit.holdExpiresAt;
                const isExpired = holdExpiresAt ? new Date(holdExpiresAt) <= new Date() : false;
                const entityName = deposit.entityName ?? 'Unknown';
                const userEmail = deposit.userEmail ?? '';
                const amount = deposit.amount ? Number(deposit.amount) : 0;
                const currency = deposit.currency || 'EUR';

                return (
                  <div
                    key={deposit.id}
                    className={`p-4 rounded-xl border ${
                      amlSelectedIds.has(deposit.id)
                        ? 'bg-emerald-500/5 border-emerald-500/20'
                        : 'bg-navy-700/50 border-navy-700'
                    }`}
                  >
                    <div className="flex items-start justify-between gap-4">
                      <input
                        type="checkbox"
                        checked={amlSelectedIds.has(deposit.id)}
                        onChange={() => {
                          setAmlSelectedIds(prev => {
                            const next = new Set(prev);
                            if (next.has(deposit.id)) next.delete(deposit.id);
                            else next.add(deposit.id);
                            return next;
                          });
                        }}
                        className="w-4 h-4 rounded border-navy-600 bg-navy-800 accent-emerald-500 cursor-pointer mt-1 flex-shrink-0"
                        aria-label={`Select ${entityName}`}
                      />
                      <div className="flex-1">
                        <div className="flex items-center gap-3 mb-2">
                          <h3 className="font-semibold text-white">
                            {entityName}
                          </h3>
                          <Badge variant="warning">AML Hold</Badge>
                          {isExpired && (
                            <Badge variant="success">Ready to Clear</Badge>
                          )}
                        </div>
                        <div className="grid grid-cols-2 gap-4 text-sm">
                          <div>
                            <span className="text-navy-400">Amount:</span>
                            <span className="ml-2 text-navy-200 font-semibold">
                              €{amount.toLocaleString(undefined, { minimumFractionDigits: 2 })} {currency}
                            </span>
                          </div>
                          <div>
                            <span className="text-navy-400">User:</span>
                            <span className="ml-2 text-navy-200">{userEmail}</span>
                          </div>
                          {holdExpiresAt && (
                            <div className="flex items-center gap-1">
                              <Timer className="w-4 h-4 text-navy-400" />
                              <span className="text-navy-400">Hold expires:</span>
                              <span className={`ml-1 font-medium ${isExpired ? 'text-emerald-600' : 'text-amber-600'}`}>
                                {isExpired ? 'Expired' : new Date(holdExpiresAt).toLocaleDateString()}
                              </span>
                            </div>
                          )}
                        </div>
                      </div>
                      <div className="flex items-center gap-2">
                        <Button
                          variant="ghost"
                          size="sm"
                          onClick={() => handleRejectAML(deposit.id)}
                          loading={actionLoading === `aml-reject-${deposit.id}`}
                          disabled={actionLoading !== null}
                          className="text-red-500 hover:text-red-400 hover:bg-red-500/10"
                        >
                          <XCircle className="w-4 h-4 mr-1" />
                          Reject
                        </Button>
                        <Button
                          variant="primary"
                          size="sm"
                          onClick={() => handleClearAML(deposit.id)}
                          loading={actionLoading === `aml-clear-${deposit.id}`}
                          disabled={actionLoading !== null}
                          className={isExpired ? 'bg-emerald-500 hover:bg-emerald-600' : ''}
                        >
                          <CheckCircle className="w-4 h-4 mr-1" />
                          {isExpired ? 'Clear' : 'Force Clear'}
                        </Button>
                      </div>
                    </div>
                  </div>
                );
              })}
            </div>
          )}
        </Card>
      )}

      {activeSubpage === 'settlements' && (
        <Card>
          <div className="flex items-center gap-2 mb-6">
            <Timer className="w-5 h-5 text-emerald-500" />
            <h2 className="text-lg font-semibold text-white">
              Settlement Queue
            </h2>
            <Badge variant="info" className="ml-2">
              {settlementBatches.length} pending
            </Badge>
          </div>

          {loading ? (
            <div className="space-y-4">
              {[...Array(3)].map((_, i) => (
                <div key={i} className="animate-pulse p-4 bg-navy-700 rounded-xl">
                  <div className="h-4 bg-navy-600 rounded w-1/3 mb-2" />
                  <div className="h-3 bg-navy-600 rounded w-1/2" />
                </div>
              ))}
            </div>
          ) : settlementBatches.length === 0 ? (
            <div className="text-center py-12 text-navy-400">
              <Timer className="w-12 h-12 mx-auto mb-4 opacity-50" />
              <p>No settlements pending</p>
            </div>
          ) : (
            <div className="space-y-4">
              {settlementBatches.map((batch) => {
                const expectedDate = new Date(batch.expectedSettlementDate);
                const now = new Date();
                const diffMs = expectedDate.getTime() - now.getTime();
                const isOverdue = diffMs < 0;
                const absDiffMs = Math.abs(diffMs);
                const days = Math.floor(absDiffMs / (1000 * 60 * 60 * 24));
                const hours = Math.floor((absDiffMs % (1000 * 60 * 60 * 24)) / (1000 * 60 * 60));
                const timeLabel = isOverdue
                  ? `Overdue ${days > 0 ? `${days}d ` : ''}${hours}h`
                  : `${days > 0 ? `${days}d ` : ''}${hours}h remaining`;

                const typeLabel = batch.settlementType === 'CEA_PURCHASE'
                  ? 'CEA Purchase' : 'Swap CEA→EUA';
                const typeVariant = batch.settlementType === 'CEA_PURCHASE'
                  ? 'info' as const : 'warning' as const;

                return (
                  <div
                    key={batch.id}
                    className="p-4 bg-navy-700/50 rounded-xl border border-navy-700"
                  >
                    <div className="flex items-start justify-between gap-4">
                      <div className="flex-1">
                        <div className="flex items-center gap-3 mb-2">
                          <h3 className="font-semibold text-white">
                            {batch.entityName}
                          </h3>
                          <Badge variant={typeVariant}>{typeLabel}</Badge>
                          <Badge variant={
                            batch.status === 'PENDING' ? 'warning' :
                            batch.status === 'IN_TRANSIT' ? 'info' :
                            batch.status === 'AT_CUSTODY' ? 'info' :
                            'default'
                          }>
                            {batch.status.replace(/_/g, ' ')}
                          </Badge>
                        </div>
                        <div className="grid grid-cols-2 sm:grid-cols-4 gap-4 text-sm">
                          <div>
                            <span className="text-navy-400">Quantity:</span>
                            <span className="ml-2 text-navy-200 font-semibold">
                              {batch.quantity.toLocaleString()} tCO₂
                            </span>
                          </div>
                          <div>
                            <span className="text-navy-400">Value:</span>
                            <span className="ml-2 text-navy-200 font-semibold">
                              €{batch.totalValueEur.toLocaleString(undefined, { minimumFractionDigits: 2 })}
                            </span>
                          </div>
                          <div>
                            <span className="text-navy-400">User:</span>
                            <span className="ml-2 text-navy-200">
                              {batch.userEmail ?? '—'}
                            </span>
                          </div>
                          <div className="flex items-center gap-1">
                            <Timer className="w-4 h-4 text-navy-400" />
                            <span className={`font-medium ${isOverdue ? 'text-red-500' : 'text-emerald-600'}`}>
                              {timeLabel}
                            </span>
                          </div>
                        </div>
                        {batch.userRole && (
                          <div className="mt-2">
                            <Badge variant="default" className="text-xs">
                              {batch.userRole.replace(/_/g, ' ')}
                            </Badge>
                          </div>
                        )}
                      </div>
                      <div className="flex items-center">
                        <Button
                          variant="primary"
                          size="sm"
                          onClick={() => handleSettleNow(batch.id)}
                          loading={actionLoading === `settle-${batch.id}`}
                          disabled={actionLoading !== null}
                          className="bg-emerald-500 hover:bg-emerald-600"
                        >
                          <CheckCircle className="w-4 h-4 mr-1" />
                          Settle Now
                        </Button>
                      </div>
                    </div>
                  </div>
                );
              })}
            </div>
          )}
        </Card>
      )}

      <DocumentViewerModal
        document={showDocumentViewer}
        documentContentUrl={documentContentUrl}
        documentError={documentError}
        documentLoading={documentLoading}
        onClose={handleCloseDocumentViewer}
        onDownload={handleDownloadDocument}
        onRetry={showDocumentViewer ? () => loadDocumentContent(showDocumentViewer.id) : undefined}
      />

      <IPLookupModal
        isOpen={showIpModal}
        onClose={() => {
          setShowIpModal(false);
          setIpLookupData(null);
        }}
        ipLookupData={ipLookupData}
        ipLookupLoading={ipLookupLoading}
      />
    </BackofficeLayout>
  );
}
