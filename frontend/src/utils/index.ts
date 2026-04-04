import { clsx, type ClassValue } from 'clsx';
import { twMerge } from 'tailwind-merge';

// Combine class names with Tailwind merge
export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs));
}

/**
 * Format a number as currency. Callers must pass a number; for missing amount
 * in UI, display "—" or N/A instead of formatCurrency(0) to avoid masking invalid data.
 * Platform default: EUR.
 */
export function formatCurrency(
  value: number,
  currency: string = 'EUR',
  locale: string = 'en-US'
): string {
  return new Intl.NumberFormat(locale, {
    style: 'currency',
    currency,
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  }).format(value);
}

// Format large numbers with abbreviations
export function formatCompact(value: number): string {
  if (value >= 1000000) {
    return `${(value / 1000000).toFixed(1)}M`;
  }
  if (value >= 1000) {
    return `${(value / 1000).toFixed(1)}K`;
  }
  return value.toFixed(0);
}

// Format percentage
export function formatPercent(value: number, decimals: number = 2): string {
  const sign = value >= 0 ? '+' : '';
  return `${sign}${value.toFixed(decimals)}%`;
}

// Format quantity with proper thousand separators
export function formatQuantity(value: number | undefined | null): string {
  // Add null-safety to prevent NaN display
  if (value === undefined || value === null || isNaN(value)) {
    return '0';
  }

  return new Intl.NumberFormat('en-US', {
    minimumFractionDigits: 0,
    maximumFractionDigits: 2,
  }).format(value);
}

/**
 * Format CEA/EUA certificate quantity (whole numbers only, no fractional certificates).
 * Use for all certificate balance, volume, and quantity display.
 */
export function formatCertificateQuantity(value: number | undefined | null): string {
  if (value === undefined || value === null || isNaN(value)) {
    return '0';
  }
  return new Intl.NumberFormat('en-US', {
    minimumFractionDigits: 0,
    maximumFractionDigits: 0,
  }).format(Math.round(value));
}

/**
 * Parse a UTC datetime string from the API into a Date object.
 * The backend returns naive UTC timestamps without 'Z' (e.g. "2026-04-04T04:17:19").
 * Without 'Z', JS treats them as local time — wrong in any non-UTC timezone.
 * This helper appends 'Z' when missing to force correct UTC interpretation.
 */
export function parseUtcDate(str: string | null | undefined): Date | null {
  if (!str) return null;
  const s = str.endsWith('Z') || str.includes('+') || (str.includes('-', 11)) ? str : str + 'Z';
  const d = new Date(s);
  return isNaN(d.getTime()) ? null : d;
}

// Format date (locale date string)
export function formatDate(date: string | Date, options?: Intl.DateTimeFormatOptions): string {
  const d = typeof date === 'string' ? (parseUtcDate(date) ?? new Date(date)) : date;
  if (Number.isNaN(d.getTime())) return '—';
  return d.toLocaleDateString('en-US', {
    year: 'numeric',
    month: 'short',
    day: 'numeric',
    ...options,
  });
}

/**
 * Formats a date as relative time (e.g. "5m ago", "2h ago", "Jan 28").
 * Returns '—' when date is null or undefined (safe for missing API fields like created_at).
 */
export function formatRelativeTime(date: string | Date | null | undefined): string {
  if (date == null) return '—';
  const now = new Date();
  // Ensure UTC interpretation if no timezone present in ISO string
  let dateString = typeof date === 'string' ? date : date.toISOString();
  if (typeof date === 'string' && !date.endsWith('Z') && !date.includes('+') && !date.includes('-', 10)) {
    dateString = date + 'Z';
  }
  const then = new Date(dateString);
  const diffMs = now.getTime() - then.getTime();
  const diffMins = Math.floor(diffMs / 60000);
  const diffHours = Math.floor(diffMs / 3600000);
  const diffDays = Math.floor(diffMs / 86400000);

  if (diffMins < 1) return 'just now';
  if (diffMins < 60) return `${diffMins}m ago`;
  if (diffHours < 24) return `${diffHours}h ago`;
  if (diffDays < 7) return `${diffDays}d ago`;

  return then.toLocaleDateString('en-US', {
    month: 'short',
    day: 'numeric',
  });
}

// Generate gradient based on value
export function getPriceChangeColor(change: number): string {
  if (change > 0) return 'text-emerald-600';
  if (change < 0) return 'text-red-500';
  return 'text-navy-500';
}

// Get certificate type color
export function getCertificateColor(type: 'EUA' | 'CEA'): {
  bg: string;
  text: string;
  border: string;
} {
  if (type === 'EUA') {
    return {
      bg: 'bg-blue-100',
      text: 'text-blue-700',
      border: 'border-blue-200',
    };
  }
  return {
    bg: 'bg-amber-100',
    text: 'text-amber-700',
    border: 'border-amber-200',
  };
}

// Validate email
export function isValidEmail(email: string): boolean {
  const emailRegex = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
  return emailRegex.test(email);
}

// Check if corporate email (not personal)
export function isCorporateEmail(email: string): boolean {
  const personalDomains = [
    'gmail.com',
    'yahoo.com',
    'hotmail.com',
    'outlook.com',
    'aol.com',
    'icloud.com',
    'mail.com',
    'protonmail.com',
  ];
  const domain = email.split('@')[1]?.toLowerCase();
  return domain ? !personalDomains.includes(domain) : false;
}

// Truncate text
export function truncate(text: string, length: number): string {
  if (text.length <= length) return text;
  return `${text.slice(0, length)}...`;
}

// Debounce function
export function debounce<T extends (...args: unknown[]) => void>(
  func: T,
  wait: number
): (...args: Parameters<T>) => void {
  let timeout: ReturnType<typeof setTimeout>;
  return (...args: Parameters<T>) => {
    clearTimeout(timeout);
    timeout = setTimeout(() => func(...args), wait);
  };
}

// Generate random ID
export function generateId(): string {
  return Math.random().toString(36).substring(2, 9);
}

// Sleep utility
export function sleep(ms: number): Promise<void> {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

// Export logger
export { logger } from './logger';

// Export sanitization utilities
export {
  sanitizeString,
  sanitizeHtml,
  sanitizeEmail,
  sanitizeNumber,
  sanitizeObject,
  sanitizeFormData,
  isValidCssVariableName,
  isValidCssValue,
  sanitizeCssVariables,
} from './sanitize';

// Export data transformation utilities
export {
  transformKeysToCamelCase,
  transformKeysToSnakeCase,
} from './dataTransform';

// Export redirect utilities
export { getPostLoginRedirect } from './redirect';

// Export effective role (admin role simulation)
export { getEffectiveRole, USER_ROLES } from './effectiveRole';

// Export user utilities
export { formatUserName, getUserInitials } from './userUtils';

// Export role badge helpers (client status / user_role)
export { clientStatusVariant, type ClientStatusVariant } from './roleBadge';

// Export contact request helpers (pending list filter)
export {
  isPendingContactRequest,
  PENDING_CONTACT_REQUEST_ROLES,
} from './contactRequest';

// Export API error message helper
export { getApiErrorMessage } from './errors';
