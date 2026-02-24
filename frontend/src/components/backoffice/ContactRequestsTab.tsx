/**
 * Contact Requests Tab Component
 *
 * Displays and manages contact requests (join requests and NDA submissions) in compact list rows
 * (Entity, Name, Submitted + View / Approve & Create User / Reject / Delete). Each row shows entity_name and
 * contact_name (fallback "---" when missing). View opens ContactRequestViewModal with all fields and NDA
 * open-NDA button; onIpLookup is passed to the modal for the IP Lookup link. View/Approve/Reject/Delete
 * use aria-label fallbacks (entity_name ?? contact_email ?? id ?? 'contact request'). Real-time WebSocket updates.
 *
 * For introducer requests, shows NDA lifecycle badges and conditional buttons based on introducerNdaStatus.
 *
 * @component
 */

import { useState } from 'react';
import { motion } from 'framer-motion';
import { Users, Eye, Trash2, CheckCircle2 } from 'lucide-react';
import { Button, Badge } from '../common';
import { Typography } from '../common/Typography';
import { clientStatusVariant } from '../../utils/roleBadge';
import { ApproveInviteModal } from './ApproveInviteModal';
import { ContactRequestViewModal } from './ContactRequestViewModal';
import { ConfirmationModal } from '../common/ConfirmationModal';
import { formatRelativeTime, formatDate } from '../../utils';
import type { ContactRequest } from '../../types/backoffice';

interface ContactRequestsTabProps {
  contactRequests: ContactRequest[];
  loading: boolean;
  connectionStatus: 'connected' | 'connecting' | 'disconnected' | 'error';
  onRefresh: () => void;
  onApprove: (requestId: string) => void;
  onReject: (requestId: string) => void;
  onDelete: (requestId: string) => void;
  onOpenNDA: (requestId: string) => Promise<void>;
  onIpLookup: (ip: string) => void;
  onOpenUserNDA?: (userId: string) => Promise<void>;
  onApproveIntroducer?: (userId: string) => void;
  onSendBuyerNDA?: (requestId: string) => void;
  onAcceptNDA?: (requestId: string) => Promise<void>;
  onApproveBuyerNDA?: (userId: string) => void;
  actionLoading: string | null;
}

export function ContactRequestsTab({
  contactRequests,
  loading,
  connectionStatus: _connectionStatus, // Reserved for future use
  onRefresh: _onRefresh, // Reserved for future use
  onApprove,
  onReject,
  onDelete,
  onOpenNDA,
  onOpenUserNDA,
  onIpLookup,
  onApproveIntroducer,
  onSendBuyerNDA,
  onAcceptNDA,
  onApproveBuyerNDA,
  actionLoading,
}: ContactRequestsTabProps) {
  // Suppress unused variable warnings for reserved parameters
  void _connectionStatus;
  void _onRefresh;

  const [approveModalRequest, setApproveModalRequest] = useState<ContactRequest | null>(null);
  const [viewModalRequest, setViewModalRequest] = useState<ContactRequest | null>(null);
  const [deleteConfirmRequest, setDeleteConfirmRequest] = useState<ContactRequest | null>(null);

  const handleApproveClick = (request: ContactRequest) => {
    setApproveModalRequest(request);
  };

  const handleApproveModalSuccess = () => {
    if (approveModalRequest) {
      onApprove(approveModalRequest.id);
    }
    setApproveModalRequest(null);
  };

  const handleDeleteClick = (request: ContactRequest) => {
    setDeleteConfirmRequest(request);
  };

  const confirmDeleteRequest = () => {
    if (deleteConfirmRequest) {
      onDelete(deleteConfirmRequest.id);
      setDeleteConfirmRequest(null);
    }
  };

  const isIntroducerWithStatus = (request: ContactRequest) =>
    request.requestFlow === 'introducer' && request.introducerNdaStatus;

  const ariaName = (request: ContactRequest) =>
    request.entityName ?? request.contactEmail ?? request.id ?? 'contact request';

  return (
    <>
      <motion.div
        initial={{ opacity: 0, y: 20 }}
        animate={{ opacity: 1, y: 0 }}
      >
        <div className="rounded-xl border-2 border-navy-700 py-6 px-4 bg-navy-800/50">
          {loading ? (
            <div className="space-y-2">
              {[...Array(3)].map((_, i) => (
                <div key={i} className="card_contact_request_list animate-pulse">
                  <div className="h-4 bg-navy-600 rounded w-1/3" />
                  <div className="h-4 bg-navy-600 rounded w-24" />
                </div>
              ))}
            </div>
          ) : contactRequests.length > 0 ? (
            <div className="space-y-2">
              {contactRequests.map((request) => (
                <div
                  key={request.id}
                  className={`card_contact_request_list ${
                    request.introducerNdaStatus === 'uploaded' || request.buyerNdaStatus === 'uploaded'
                      ? 'bg-emerald-500/5 border border-emerald-500/20 rounded-lg'
                      : ''
                  }`}
                >
                  <div className="flex flex-wrap items-center gap-x-4 gap-y-1 min-w-0">
                    <span className="flex items-center gap-1.5 shrink-0">
                      <Typography as="span" variant="sectionLabel" color="muted">
                        Entity:
                      </Typography>
                      <Typography as="span" variant="bodySmall" color="primary" className="font-medium">
                        {request.entityName ?? '---'}
                      </Typography>
                    </span>
                    <span className="flex items-center gap-1.5 shrink-0">
                      <Typography as="span" variant="sectionLabel" color="muted">
                        Name:
                      </Typography>
                      <Typography as="span" variant="bodySmall" color="primary">
                        {[request.contactFirstName, request.contactLastName].filter(Boolean).join(' ') || request.contactName || '---'}
                      </Typography>
                    </span>
                    <span className="flex items-center gap-1.5 shrink-0">
                      <Typography as="span" variant="sectionLabel" color="muted">
                        Submitted:
                      </Typography>
                      <Typography as="span" variant="bodySmall" color="primary">
                        {request.createdAt ? formatDate(request.createdAt) : '---'}
                      </Typography>
                    </span>
                    <Badge
                      variant={request.requestFlow === 'introducer'
                        ? clientStatusVariant(request.introducerNdaStatus === 'attached' || request.introducerNdaStatus === 'uploaded' ? 'INTRODUCER' : 'PREINTRODUCER')
                        : clientStatusVariant(request.userRole)}
                      className="shrink-0 text-xs"
                    >
                      {request.requestFlow === 'introducer'
                        ? (request.introducerNdaStatus === 'attached' || request.introducerNdaStatus === 'uploaded'
                          ? 'INTRODUCER'
                          : 'PREINTRODUCER')
                        : (request.userRole ?? '---')}
                    </Badge>
                    {request.referralCodeUsed ? (
                      <Badge variant="info" className="shrink-0 text-xs">Referred</Badge>
                    ) : request.requestFlow === 'introducer' ? (
                      <Badge variant="default" className="shrink-0 text-xs">Direct</Badge>
                    ) : null}
                    {/* Introducer NDA status badge */}
                    {request.introducerNdaStatus === 'sent' && (
                      <Badge variant="warning" className="shrink-0 text-xs">Awaiting NDA</Badge>
                    )}
                    {request.introducerNdaStatus === 'uploaded' && (
                      <Badge variant="success" className="shrink-0 text-xs">NDA Uploaded</Badge>
                    )}
                    {request.introducerNdaStatus === 'attached' && (
                      <Badge variant="success" className="shrink-0 text-xs">NDA Attached</Badge>
                    )}
                    {/* Buyer NDA status badges */}
                    {request.requestFlow === 'buyer' && request.buyerNdaStatus === 'sent' && (
                      <span className="text-xs px-1.5 py-0.5 rounded bg-amber-500/20 text-amber-400 border border-amber-500/30">
                        Awaiting NDA
                      </span>
                    )}
                    {request.requestFlow === 'buyer' && request.buyerNdaStatus === 'uploaded' && (
                      <span className="text-xs px-1.5 py-0.5 rounded bg-blue-500/20 text-blue-400 border border-blue-500/30">
                        NDA Uploaded
                      </span>
                    )}
                  </div>
                  <div className="flex flex-wrap items-center gap-1.5 shrink-0">
                    <button
                      type="button"
                      onClick={() => setViewModalRequest(request)}
                      className="p-2 rounded-lg text-navy-400 hover:bg-navy-700 hover:text-navy-200 transition-colors"
                      aria-label={`View details for ${ariaName(request)}`}
                    >
                      <Eye className="w-4 h-4" />
                    </button>

                    {/* Introducer requests: conditional buttons based on NDA status */}
                    {isIntroducerWithStatus(request) ? (
                      <>
                        {request.introducerNdaStatus === 'attached' && (
                          <Button
                            variant="primary"
                            size="sm"
                            onClick={() => handleApproveClick(request)}
                            loading={actionLoading === `approve-${request.id}`}
                            aria-label={`Approve and create introducer for ${ariaName(request)}`}
                          >
                            <CheckCircle2 className="w-3.5 h-3.5 mr-1" />
                            Approve & Create Introducer
                          </Button>
                        )}
                        {request.introducerNdaStatus === 'uploaded' && onApproveIntroducer && request.introducerUserId && (
                          <Button
                            variant="primary"
                            size="sm"
                            onClick={() => onApproveIntroducer(request.introducerUserId!)}
                            loading={actionLoading === `approve-introducer-${request.introducerUserId}`}
                            aria-label={`Approve NDA for ${ariaName(request)}`}
                          >
                            <CheckCircle2 className="w-3.5 h-3.5 mr-1" />
                            Approve NDA
                          </Button>
                        )}
                        {/* Reject is available for all non-approved statuses */}
                        <Button
                          variant="secondary"
                          size="sm"
                          className="text-red-500 hover:bg-red-500/20"
                          onClick={() => onReject(request.id)}
                          loading={actionLoading === `reject-${request.id}`}
                          aria-label={`Reject request from ${ariaName(request)}`}
                        >
                          Reject
                        </Button>
                      </>
                    ) : (
                      /* Non-introducer (buyer) requests: conditional buttons based on role & NDA status */
                      <>
                        {/* PRE_NDA status: buyer without NDA */}
                        {request.userRole === 'PRE_NDA' && (
                          <>
                            {(!request.buyerNdaStatus || request.buyerNdaStatus === 'not_sent') && onSendBuyerNDA && (
                              <button
                                onClick={() => onSendBuyerNDA(request.id)}
                                disabled={actionLoading === request.id}
                                className="px-2.5 py-1 rounded-md text-xs font-medium bg-amber-500/20 text-amber-400 hover:bg-amber-500/30 border border-amber-500/30 transition-colors disabled:opacity-50"
                                aria-label={`Send NDA to ${ariaName(request)}`}
                              >
                                Send NDA
                              </button>
                            )}
                            {request.buyerNdaStatus === 'sent' && (
                              <span className="px-2.5 py-1 text-xs font-medium text-blue-400">
                                Awaiting NDA
                              </span>
                            )}
                            {request.buyerNdaStatus === 'uploaded' && request.buyerUserId && onApproveBuyerNDA && (
                              <Button
                                variant="primary"
                                size="sm"
                                onClick={() => onApproveBuyerNDA(request.buyerUserId!)}
                                loading={actionLoading === `approve-buyer-nda-${request.buyerUserId}`}
                                aria-label={`Approve buyer NDA for ${ariaName(request)}`}
                              >
                                <CheckCircle2 className="w-3.5 h-3.5 mr-1" />
                                Approve NDA
                              </Button>
                            )}
                          </>
                        )}

                        {/* NDA status: buyer with NDA */}
                        {request.userRole === 'NDA' && (
                          <>
                            {request.ndaAccepted ? (
                              <Button
                                variant="primary"
                                size="sm"
                                onClick={() => handleApproveClick(request)}
                                loading={actionLoading === `approve-${request.id}`}
                                aria-label={`Approve and create user for ${ariaName(request)}`}
                              >
                                Approve & Create User
                              </Button>
                            ) : (
                              <span className="px-2.5 py-1 text-xs italic text-navy-400">
                                Review NDA in details
                              </span>
                            )}
                          </>
                        )}

                        {/* Legacy 'new' status: keep original approve button */}
                        {request.userRole === 'new' && (
                          <Button
                            variant="primary"
                            size="sm"
                            onClick={() => handleApproveClick(request)}
                            loading={actionLoading === `approve-${request.id}`}
                            aria-label={`Approve and create user for ${ariaName(request)}`}
                          >
                            Approve & Create User
                          </Button>
                        )}

                        {/* Reject is available for all buyer states */}
                        {(request.userRole === 'PRE_NDA' || request.userRole === 'NDA' || request.userRole === 'new') && (
                          <Button
                            variant="secondary"
                            size="sm"
                            className="text-red-500 hover:bg-red-500/20"
                            onClick={() => onReject(request.id)}
                            loading={actionLoading === `reject-${request.id}`}
                            aria-label={`Reject request from ${ariaName(request)}`}
                          >
                            Reject
                          </Button>
                        )}
                      </>
                    )}

                    <button
                      type="button"
                      onClick={() => handleDeleteClick(request)}
                      disabled={!!actionLoading}
                      className="p-2 rounded-lg text-navy-400 hover:bg-navy-700 hover:text-red-400 transition-colors disabled:opacity-50"
                      aria-label={`Delete request from ${ariaName(request)}`}
                    >
                      <Trash2 className="w-4 h-4" />
                    </button>
                  </div>
                </div>
              ))}
            </div>
          ) : (
            <div className="text-center py-12">
              <Users className="w-12 h-12 text-navy-600 mx-auto mb-4" />
              <p className="text-navy-400">No contact requests</p>
            </div>
          )}
        </div>
      </motion.div>

      {/* Approve & Invite Modal */}
      {approveModalRequest && (
        <ApproveInviteModal
          contactRequest={{
            id: approveModalRequest.id,
            entityName: approveModalRequest.entityName,
            contactEmail: approveModalRequest.contactEmail,
            contactName: approveModalRequest.contactName,
            contactFirstName: approveModalRequest.contactFirstName,
            contactLastName: approveModalRequest.contactLastName,
            position: approveModalRequest.position,
            ndaFileName: approveModalRequest.ndaFileName,
            submitterIp: approveModalRequest.submitterIp,
            userRole: approveModalRequest.userRole,
            requestFlow: approveModalRequest.requestFlow,
            notes: approveModalRequest.notes,
            createdAt: approveModalRequest.createdAt,
          }}
          isOpen={!!approveModalRequest}
          onClose={() => setApproveModalRequest(null)}
          onSuccess={handleApproveModalSuccess}
        />
      )}

      {/* View contact request details modal */}
      <ContactRequestViewModal
        request={viewModalRequest}
        isOpen={!!viewModalRequest}
        onClose={() => setViewModalRequest(null)}
        onOpenNDA={onOpenNDA}
        onOpenUserNDA={onOpenUserNDA}
        onIpLookup={onIpLookup}
        openNDALoading={actionLoading === `open-${viewModalRequest?.id}`}
        openUserNDALoading={actionLoading?.startsWith('open-user-nda-')}
        onAcceptNDA={onAcceptNDA}
        acceptNDALoading={actionLoading === viewModalRequest?.id}
      />

      {/* Delete Confirmation Modal */}
      <ConfirmationModal
        isOpen={!!deleteConfirmRequest}
        onClose={() => setDeleteConfirmRequest(null)}
        onConfirm={confirmDeleteRequest}
        title="Delete Contact Request"
        message="This action cannot be undone. The contact request will be permanently deleted from the database."
        confirmText="Delete Request"
        cancelText="Cancel"
        variant="danger"
        requireConfirmation={deleteConfirmRequest?.entityName}
        details={deleteConfirmRequest ? [
          { label: 'Company', value: deleteConfirmRequest.entityName },
          { label: 'Contact', value: deleteConfirmRequest.contactEmail },
          { label: 'Status', value: deleteConfirmRequest.userRole },
          { label: 'Submitted', value: formatRelativeTime(deleteConfirmRequest.createdAt) },
        ] : []}
        loading={actionLoading === `delete-${deleteConfirmRequest?.id}`}
      />
    </>
  );
}
