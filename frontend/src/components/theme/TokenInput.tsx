import { useState, useEffect, useCallback } from 'react';
import { RotateCcw } from 'lucide-react';
import { useThemeTokenStore } from '../../stores/useStore';
import { getCurrentTokenValue, colorToHex, parseColorWithAlpha } from '../../utils/cssTokens';
import type { TokenConfig } from '../../theme/tokens';

interface TokenInputProps {
  token: TokenConfig;
}

/**
 * Individual token editor input.
 * Shows current value with appropriate input type (color picker or text).
 * Supports live preview and reset to default.
 */
export function TokenInput({ token }: TokenInputProps) {
  const { overrides, setOverride, resetOverride } = useThemeTokenStore();
  const isOverridden = token.key in overrides;

  // Get current computed value (includes overrides applied via CSS)
  const [computedValue, setComputedValue] = useState('');

  // Update computed value on mount and when overrides change
  useEffect(() => {
    const value = getCurrentTokenValue(token.key);
    setComputedValue(value);
  }, [token.key, overrides]);

  // Local state for input value
  const [localValue, setLocalValue] = useState('');

  useEffect(() => {
    // Initialize from override or computed
    if (isOverridden) {
      setLocalValue(overrides[token.key]);
    } else {
      setLocalValue(computedValue);
    }
  }, [isOverridden, overrides, token.key, computedValue]);

  // Handle value change with live preview
  const handleChange = useCallback(
    (value: string) => {
      setLocalValue(value);
      setOverride(token.key, value);
    },
    [token.key, setOverride]
  );

  // Handle reset to default
  const handleReset = useCallback(() => {
    resetOverride(token.key);
    // Re-read computed value after reset
    setTimeout(() => {
      const value = getCurrentTokenValue(token.key);
      setComputedValue(value);
      setLocalValue(value);
    }, 0);
  }, [token.key, resetOverride]);

  // Render color input
  if (token.type === 'color') {
    const { alpha } = parseColorWithAlpha(localValue);
    const displayHex = colorToHex(localValue);

    return (
      <div className="flex items-center gap-3 py-2 px-3 rounded-lg bg-navy-800/50 hover:bg-navy-800 transition-colors group">
        {/* Label */}
        <span className="text-sm text-navy-300 w-36 truncate" title={token.key}>
          {token.label}
        </span>

        {/* Color preview box */}
        <div
          className={`w-8 h-8 rounded border border-navy-600 flex-shrink-0 ${!localValue ? 'bg-navy-900' : ''}`}
          style={localValue ? { backgroundColor: localValue } : undefined}
        />

        {/* Color picker (native) */}
        <input
          type="color"
          value={displayHex}
          onChange={(e) => {
            // Preserve alpha if original had it
            if (alpha < 1) {
              const r = parseInt(e.target.value.slice(1, 3), 16);
              const g = parseInt(e.target.value.slice(3, 5), 16);
              const b = parseInt(e.target.value.slice(5, 7), 16);
              handleChange(`rgba(${r}, ${g}, ${b}, ${alpha})`);
            } else {
              handleChange(e.target.value);
            }
          }}
          className="w-8 h-8 rounded cursor-pointer border-0 bg-transparent"
          title="Click to pick color"
        />

        {/* Hex/value text input */}
        <input
          type="text"
          value={localValue}
          onChange={(e) => handleChange(e.target.value)}
          className="flex-1 min-w-0 px-2 py-1 text-sm font-mono bg-navy-900 border border-navy-700 rounded text-white placeholder-navy-500 focus:outline-none focus:border-emerald-500"
          placeholder={token.key}
        />

        {/* Modified indicator + Reset button */}
        <div className="flex items-center gap-2">
          {isOverridden && (
            <span className="text-xs text-amber-400 font-medium">modified</span>
          )}
          <button
            onClick={handleReset}
            disabled={!isOverridden}
            className={`p-1.5 rounded transition-colors ${
              isOverridden
                ? 'text-navy-400 hover:text-white hover:bg-navy-700'
                : 'text-navy-700 cursor-not-allowed'
            }`}
            title="Reset to default"
          >
            <RotateCcw className="w-4 h-4" />
          </button>
        </div>
      </div>
    );
  }

  // Render size/length input
  return (
    <div className="flex items-center gap-3 py-2 px-3 rounded-lg bg-navy-800/50 hover:bg-navy-800 transition-colors group">
      {/* Label */}
      <span className="text-sm text-navy-300 w-36 truncate" title={token.key}>
        {token.label}
      </span>

      {/* Size preview */}
      <div className="w-8 h-8 rounded border border-navy-600 flex-shrink-0 flex items-center justify-center bg-navy-900">
        <div
          className="bg-emerald-500 rounded-sm"
          style={{
            width: `min(${localValue || '0.5rem'}, 24px)`,
            height: `min(${localValue || '0.5rem'}, 24px)`,
          }}
        />
      </div>

      {/* Value input */}
      <input
        type="text"
        value={localValue}
        onChange={(e) => handleChange(e.target.value)}
        className="flex-1 min-w-0 px-2 py-1 text-sm font-mono bg-navy-900 border border-navy-700 rounded text-white placeholder-navy-500 focus:outline-none focus:border-emerald-500"
        placeholder="e.g., 1rem, 16px"
      />

      {/* CSS variable name display */}
      <code className="hidden lg:block text-xs text-navy-500 font-mono truncate max-w-32">
        {token.key}
      </code>

      {/* Modified indicator + Reset button */}
      <div className="flex items-center gap-2">
        {isOverridden && (
          <span className="text-xs text-amber-400 font-medium">modified</span>
        )}
        <button
          onClick={handleReset}
          disabled={!isOverridden}
          className={`p-1.5 rounded transition-colors ${
            isOverridden
              ? 'text-navy-400 hover:text-white hover:bg-navy-700'
              : 'text-navy-700 cursor-not-allowed'
          }`}
          title="Reset to default"
        >
          <RotateCcw className="w-4 h-4" />
        </button>
      </div>
    </div>
  );
}
