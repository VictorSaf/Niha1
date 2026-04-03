import { useEffect, useRef, useCallback } from 'react';
import { useBackofficeStore, KYCDocumentBackoffice } from '../stores/useStore';
import { backofficeRealtimeApi, adminApi, backofficeApi, BackofficeWebSocketMessage } from '../services/api';
import type { ContactRequestResponse } from '../types';
import { isPlainObject } from '../utils/dataTransform';
import { logger } from '../utils/logger';

const RECONNECT_DELAY = 3000; // 3 seconds
const POLLING_INTERVAL = 30000; // 30 seconds fallback polling

/** Helper to safely convert unknown value to string */
function toStringOrUndefined(value: unknown): string | undefined {
  if (value === null || value === undefined) return undefined;
  return String(value);
}

/** Ensures a plain object for key transformation (handles class instances / non-plain objects from WS). */
function ensurePlainObject<T>(obj: unknown): T {
  if (obj === null || obj === undefined) return obj as T;
  if (isPlainObject(obj)) return obj as T;
  if (typeof obj === 'object' && !Array.isArray(obj)) {
    try {
      return JSON.parse(JSON.stringify(obj)) as T;
    } catch {
      return obj as T;
    }
  }
  return obj as T;
}

/**
 * Backoffice realtime hook: WebSocket + polling for contact requests and KYC documents.
 * Contact request data from the API and WebSocket is in camelCase (transformed by axios interceptor).
 * Data is stored as-is in camelCase to match TypeScript types (entityName, contactEmail, etc.).
 */
export function useBackofficeRealtime() {
  const {
    contactRequests,
    kycDocuments,
    connectionStatus,
    lastUpdated,
    kycLastUpdated,
    setContactRequests,
    addContactRequest,
    updateContactRequest,
    removeContactRequest,
    setKYCDocuments,
    addKYCDocument,
    updateKYCDocument,
    removeKYCDocument,
    setConnectionStatus,
  } = useBackofficeStore();

  const wsRef = useRef<WebSocket | null>(null);
  const reconnectTimeoutRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const pollingIntervalRef = useRef<ReturnType<typeof setInterval> | null>(null);
  const mountedRef = useRef(true);

  // Fetch initial data
  const fetchContactRequests = useCallback(async () => {
    try {
      const response = await adminApi.getContactRequests({ per_page: 100 });
      if (mountedRef.current) {
        // API response is already in camelCase from axios interceptor
        setContactRequests(response.data as ContactRequestResponse[]);
      }
    } catch (err) {
      logger.error('Failed to fetch contact requests', err);
    }
  }, [setContactRequests]);

  // Fetch KYC documents
  const fetchKYCDocuments = useCallback(async () => {
    try {
      const documents = await backofficeApi.getKYCDocuments();
      if (mountedRef.current) {
        setKYCDocuments(documents);
      }
    } catch (err) {
      logger.error('Failed to fetch KYC documents', err);
    }
  }, [setKYCDocuments]);

  // Handle WebSocket messages
  const handleMessage = useCallback((message: BackofficeWebSocketMessage) => {
    if (!mountedRef.current) return;

    switch (message.type) {
      case 'connected':
        setConnectionStatus('connected');
        break;

      case 'heartbeat':
        // Connection is alive, nothing to do
        break;

      case 'new_request':
        if (message.data) {
          // WebSocket payload is already camelCase
          const newRequest = ensurePlainObject<ContactRequestResponse>(message.data);
          addContactRequest(newRequest);
        }
        break;

      case 'request_updated':
        if (message.data) {
          // WebSocket payload is already camelCase
          const updatedRequest = ensurePlainObject<ContactRequestResponse>(message.data);
          updateContactRequest(updatedRequest);
        }
        break;

      case 'request_removed':
        if (message.data) {
          const id = toStringOrUndefined((message.data as { id?: unknown }).id);
          if (id) removeContactRequest(id);
        }
        break;

      // KYC Document Events
      case 'kyc_document_uploaded':
        if (message.data) {
          const data = message.data;
          const documentId = toStringOrUndefined(data.document_id) ?? toStringOrUndefined(data.documentId);
          const userId = toStringOrUndefined(data.user_id) ?? toStringOrUndefined(data.userId);
          if (documentId && userId) {
            const newDoc: KYCDocumentBackoffice = {
              id: documentId,
              userId: userId,
              userEmail: toStringOrUndefined(data.user_email) ?? toStringOrUndefined(data.userEmail) ?? '',
              documentType: toStringOrUndefined(data.document_type) ?? toStringOrUndefined(data.documentType) ?? '',
              fileName: toStringOrUndefined(data.file_name) ?? toStringOrUndefined(data.fileName) ?? '',
              status: toStringOrUndefined(data.status) ?? 'pending',
              createdAt: toStringOrUndefined(data.created_at) ?? toStringOrUndefined(data.createdAt) ?? new Date().toISOString(),
            };
            addKYCDocument(newDoc);
          }
        }
        break;

      case 'kyc_document_reviewed':
        if (message.data) {
          const data = message.data;
          const documentId = toStringOrUndefined(data.document_id) ?? toStringOrUndefined(data.documentId);
          if (documentId) {
            updateKYCDocument({
              id: documentId,
              status: toStringOrUndefined(data.status),
              notes: toStringOrUndefined(data.notes),
              reviewedAt: toStringOrUndefined(data.reviewed_at) ?? toStringOrUndefined(data.reviewedAt),
            });
          }
        }
        break;

      case 'kyc_document_deleted':
        if (message.data) {
          const data = message.data;
          const documentId = toStringOrUndefined(data.document_id) ?? toStringOrUndefined(data.documentId);
          if (documentId) {
            removeKYCDocument(documentId);
          }
        }
        break;

      // Settlement Events — dispatch custom events for any listening page
      case 'new_settlement':
      case 'settlement_status_changed':
      case 'settlement_settled':
        window.dispatchEvent(new CustomEvent('nihao:settlementChanged', { detail: message.data }));
        break;

      // System Health Events
      case 'system_health_update':
        window.dispatchEvent(new CustomEvent('nihao:system_health_update', { detail: message.data }));
        break;
    }
  }, [setConnectionStatus, addContactRequest, updateContactRequest, removeContactRequest, addKYCDocument, updateKYCDocument, removeKYCDocument]);

  // Connect WebSocket with reconnection logic
  const connect = useCallback(() => {
    if (!mountedRef.current) return;
    if (wsRef.current?.readyState === WebSocket.OPEN) return;

    setConnectionStatus('connecting');

    try {
      wsRef.current = backofficeRealtimeApi.connectWebSocket(
        handleMessage,
        () => {
          // onOpen
          if (mountedRef.current) {
            setConnectionStatus('connected');
            // Clear any reconnect timeout
            if (reconnectTimeoutRef.current) {
              clearTimeout(reconnectTimeoutRef.current);
              reconnectTimeoutRef.current = null;
            }
          }
        },
        () => {
          // onClose
          if (mountedRef.current) {
            setConnectionStatus('disconnected');
            // Schedule reconnection
            reconnectTimeoutRef.current = setTimeout(connect, RECONNECT_DELAY);
          }
        },
        () => {
          // onError
          if (mountedRef.current) {
            setConnectionStatus('error');
          }
        }
      );
    } catch (err) {
      logger.error('[Backoffice WS] Connection failed', err);
      setConnectionStatus('error');
      // Schedule reconnection
      reconnectTimeoutRef.current = setTimeout(connect, RECONNECT_DELAY);
    }
  }, [handleMessage, setConnectionStatus]);

  // Initialize connection and polling fallback
  useEffect(() => {
    mountedRef.current = true;

    // Fetch initial data
    fetchContactRequests();
    fetchKYCDocuments();

    // Connect WebSocket
    connect();

    // Set up polling as fallback (less frequent than prices)
    pollingIntervalRef.current = setInterval(() => {
      fetchContactRequests();
      fetchKYCDocuments();
    }, POLLING_INTERVAL);

    return () => {
      mountedRef.current = false;

      // Clean up WebSocket properly
      if (wsRef.current) {
        try {
          wsRef.current.onerror = null;
          wsRef.current.onclose = null;
          wsRef.current.onmessage = null;
          if (wsRef.current.readyState === WebSocket.OPEN || wsRef.current.readyState === WebSocket.CONNECTING) {
            wsRef.current.close();
          }
          wsRef.current = null;
        } catch (error) {
          logger.error('Error closing backoffice WebSocket', error);
        }
      }

      // Clear timeouts
      if (reconnectTimeoutRef.current) {
        clearTimeout(reconnectTimeoutRef.current);
        reconnectTimeoutRef.current = null;
      }

      // Clear polling interval
      if (pollingIntervalRef.current) {
        clearInterval(pollingIntervalRef.current);
        pollingIntervalRef.current = null;
      }
    };
  }, [connect, fetchContactRequests, fetchKYCDocuments]);

  // Manual refresh function
  const refresh = useCallback(() => {
    fetchContactRequests();
    fetchKYCDocuments();
  }, [fetchContactRequests, fetchKYCDocuments]);

  return {
    contactRequests,
    kycDocuments,
    connectionStatus,
    lastUpdated,
    kycLastUpdated,
    refresh,
    removeContactRequest,
  };
}
