import { useState } from 'react';
import { motion } from 'framer-motion';
import {
  Sun,
  Moon,
  Check,
  AlertCircle,
  AlertTriangle,
  Info,
  TrendingUp,
  TrendingDown,
  Copy,
  Leaf,
  Wind,
  Euro,
  ChevronRight,
  Settings,
  User,
  Bell,
  Search,
  Filter,
  Download,
  Upload,
  RefreshCw,
  BarChart3,
  Activity,
} from 'lucide-react';

/**
 * NIHA CARBON PLATFORM - DESIGN SYSTEM SHOWCASE
 *
 * A comprehensive reference page displaying all standardized design tokens,
 * components, and patterns. Features split-screen light/dark mode comparison.
 */

export function DesignSystemPage() {
  const [activeSection, setActiveSection] = useState('colors');

  const sections = [
    { id: 'colors', label: 'Colors' },
    { id: 'typography', label: 'Typography' },
    { id: 'spacing', label: 'Spacing' },
    { id: 'radius', label: 'Border Radius' },
    { id: 'shadows', label: 'Shadows' },
    { id: 'buttons', label: 'Buttons' },
    { id: 'inputs', label: 'Inputs' },
    { id: 'badges', label: 'Badges' },
    { id: 'cards', label: 'Cards' },
    { id: 'tables', label: 'Tables' },
    { id: 'trading', label: 'Trading UI' },
    { id: 'icons', label: 'Icons' },
    { id: 'animations', label: 'Animations' },
  ];

  return (
    <div className="min-h-screen bg-gradient-to-br from-navy-50 via-white to-navy-100">
      {/* Header */}
      <header className="sticky top-0 z-50 border-b border-navy-200 bg-white/80 backdrop-blur-xl">
        <div className="mx-auto max-w-[1920px] px-8 py-6">
          <div className="flex items-center justify-between">
            <div>
              <h1 className="text-3xl font-bold tracking-tight text-navy-900">
                Design System
              </h1>
              <p className="mt-1 text-sm text-navy-600">
                Niha Carbon Platform • v1.0.0
              </p>
            </div>
            <div className="flex items-center gap-3">
              <button className="flex items-center gap-2 rounded-xl bg-navy-900 px-4 py-2.5 text-sm font-semibold text-white transition-all hover:bg-navy-800 hover:shadow-lg">
                <Download className="h-4 w-4" />
                Export Tokens
              </button>
            </div>
          </div>
        </div>
      </header>

      <div className="mx-auto max-w-[1920px]">
        <div className="flex">
          {/* Sidebar Navigation */}
          <nav className="sticky top-[88px] h-[calc(100vh-88px)] w-64 border-r border-navy-200 bg-white/50 p-6">
            <div className="space-y-1">
              {sections.map((section) => (
                <button
                  key={section.id}
                  onClick={() => setActiveSection(section.id)}
                  className={`flex w-full items-center gap-3 rounded-lg px-4 py-2.5 text-left text-sm font-medium transition-all ${
                    activeSection === section.id
                      ? 'bg-emerald-500 text-white shadow-lg shadow-emerald-500/25'
                      : 'text-navy-700 hover:bg-navy-100'
                  }`}
                >
                  <ChevronRight
                    className={`h-4 w-4 transition-transform ${
                      activeSection === section.id ? 'rotate-90' : ''
                    }`}
                  />
                  {section.label}
                </button>
              ))}
            </div>
          </nav>

          {/* Main Content - Split Screen */}
          <div className="flex-1">
            <div className="grid grid-cols-2 divide-x divide-navy-200">
              {/* Light Mode Column */}
              <div className="min-h-screen bg-navy-50 p-8">
                <div className="mb-8 flex items-center gap-3 rounded-xl border border-amber-200 bg-amber-50 px-4 py-3">
                  <Sun className="h-5 w-5 text-amber-600" />
                  <span className="text-sm font-semibold text-amber-900">
                    Light Mode
                  </span>
                </div>
                <div className="space-y-12">
                  <ContentSections mode="light" activeSection={activeSection} />
                </div>
              </div>

              {/* Dark Mode Column */}
              <div className="min-h-screen bg-navy-950 p-8">
                <div className="mb-8 flex items-center gap-3 rounded-xl border border-navy-700 bg-navy-900 px-4 py-3">
                  <Moon className="h-5 w-5 text-navy-400" />
                  <span className="text-sm font-semibold text-navy-200">
                    Dark Mode
                  </span>
                </div>
                <div className="space-y-12">
                  <ContentSections mode="dark" activeSection={activeSection} />
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}

// Content Sections Component
function ContentSections({ mode, activeSection }: { mode: 'light' | 'dark'; activeSection: string }) {
  const isDark = mode === 'dark';

  return (
    <>
      {/* COLORS SECTION */}
      {activeSection === 'colors' && (
        <motion.section
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          className="space-y-8"
        >
          <SectionHeader title="Color Palette" isDark={isDark} />

          {/* Background Colors */}
          <ColorGroup
            title="Background Colors"
            colors={[
              { name: 'Background', var: '--color-background', class: isDark ? 'bg-navy-900' : 'bg-navy-50' },
              { name: 'Surface', var: '--color-surface', class: isDark ? 'bg-navy-800' : 'bg-white' },
              { name: 'Surface Elevated', var: '--color-surface-elevated', class: isDark ? 'bg-navy-700' : 'bg-navy-100' },
              { name: 'Surface Muted', var: '--color-surface-muted', class: isDark ? 'bg-navy-600' : 'bg-navy-200' },
            ]}
            isDark={isDark}
          />

          {/* Text Colors */}
          <ColorGroup
            title="Text Colors"
            colors={[
              { name: 'Primary', var: '--color-text-primary', class: isDark ? 'bg-white' : 'bg-navy-900' },
              { name: 'Secondary', var: '--color-text-secondary', class: isDark ? 'bg-navy-300' : 'bg-navy-600' },
              { name: 'Muted', var: '--color-text-muted', class: isDark ? 'bg-navy-400' : 'bg-navy-500' },
            ]}
            isDark={isDark}
          />

          {/* Brand Colors - Emerald */}
          <ColorGroup
            title="Brand Colors (Emerald)"
            colors={[
              { name: 'Primary', var: '--color-primary', class: isDark ? 'bg-emerald-400' : 'bg-emerald-500' },
              { name: 'Primary Hover', var: '--color-primary-hover', class: isDark ? 'bg-emerald-500' : 'bg-emerald-600' },
              { name: 'Primary Light', var: '--color-primary-light', class: isDark ? 'bg-emerald-500/20' : 'bg-emerald-100' },
            ]}
            isDark={isDark}
          />

          {/* Certificate Colors */}
          <ColorGroup
            title="Certificate Colors"
            colors={[
              { name: 'EUA (Blue)', var: '--color-eua', class: isDark ? 'bg-blue-400' : 'bg-blue-500', icon: <Leaf className="h-4 w-4" /> },
              { name: 'CEA (Amber)', var: '--color-cea', class: isDark ? 'bg-amber-400' : 'bg-amber-500', icon: <Wind className="h-4 w-4" /> },
            ]}
            isDark={isDark}
          />

          {/* Trading Colors */}
          <ColorGroup
            title="Trading Colors"
            colors={[
              { name: 'Bid (Buy)', var: '--color-bid', class: isDark ? 'bg-emerald-400' : 'bg-emerald-500', icon: <TrendingUp className="h-4 w-4" /> },
              { name: 'Ask (Sell)', var: '--color-ask', class: isDark ? 'bg-red-400' : 'bg-red-500', icon: <TrendingDown className="h-4 w-4" /> },
            ]}
            isDark={isDark}
          />

          {/* Status Colors */}
          <ColorGroup
            title="Status Colors"
            colors={[
              { name: 'Success', var: '--color-success', class: isDark ? 'bg-emerald-400' : 'bg-emerald-500', icon: <Check className="h-4 w-4" /> },
              { name: 'Warning', var: '--color-warning', class: isDark ? 'bg-amber-400' : 'bg-amber-500', icon: <AlertTriangle className="h-4 w-4" /> },
              { name: 'Error', var: '--color-error', class: isDark ? 'bg-red-400' : 'bg-red-500', icon: <AlertCircle className="h-4 w-4" /> },
              { name: 'Info', var: '--color-info', class: isDark ? 'bg-blue-400' : 'bg-blue-500', icon: <Info className="h-4 w-4" /> },
            ]}
            isDark={isDark}
          />
        </motion.section>
      )}

      {/* TYPOGRAPHY SECTION */}
      {activeSection === 'typography' && (
        <motion.section
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          className="space-y-8"
        >
          <SectionHeader title="Typography System" isDark={isDark} />

          {/* Font Families */}
          <div className={`rounded-2xl border p-6 ${isDark ? 'border-navy-800 bg-navy-900/50' : 'border-navy-200 bg-white'}`}>
            <h3 className={`mb-6 text-lg font-bold ${isDark ? 'text-white' : 'text-navy-900'}`}>
              Font Families
            </h3>
            <div className="space-y-4">
              <div>
                <p className={`text-sm font-medium ${isDark ? 'text-navy-400' : 'text-navy-600'}`}>
                  Sans-serif (Inter)
                </p>
                <p className={`mt-2 text-2xl font-medium ${isDark ? 'text-white' : 'text-navy-900'}`} style={{ fontFamily: 'Inter, system-ui, sans-serif' }}>
                  The quick brown fox jumps over the lazy dog
                </p>
                <code className={`mt-2 block text-xs ${isDark ? 'text-navy-500' : 'text-navy-500'}`}>
                  font-family: var(--font-sans)
                </code>
              </div>
              <div>
                <p className={`text-sm font-medium ${isDark ? 'text-navy-400' : 'text-navy-600'}`}>
                  Monospace (JetBrains Mono)
                </p>
                <p className={`mt-2 font-mono text-xl ${isDark ? 'text-white' : 'text-navy-900'}`}>
                  0123456789 €99.99 | 1,234,567.89
                </p>
                <code className={`mt-2 block text-xs ${isDark ? 'text-navy-500' : 'text-navy-500'}`}>
                  font-family: var(--font-mono)
                </code>
              </div>
            </div>
          </div>

          {/* Font Sizes */}
          <div className={`rounded-2xl border p-6 ${isDark ? 'border-navy-800 bg-navy-900/50' : 'border-navy-200 bg-white'}`}>
            <h3 className={`mb-6 text-lg font-bold ${isDark ? 'text-white' : 'text-navy-900'}`}>
              Font Size Scale
            </h3>
            <div className="space-y-4">
              {[
                { size: 'xs', px: '12px', rem: '0.75rem', text: 'Extra Small' },
                { size: 'sm', px: '14px', rem: '0.875rem', text: 'Small' },
                { size: 'base', px: '16px', rem: '1rem', text: 'Base' },
                { size: 'lg', px: '18px', rem: '1.125rem', text: 'Large' },
                { size: 'xl', px: '20px', rem: '1.25rem', text: 'Extra Large' },
                { size: '2xl', px: '24px', rem: '1.5rem', text: '2X Large' },
                { size: '3xl', px: '30px', rem: '1.875rem', text: '3X Large' },
                { size: '4xl', px: '36px', rem: '2.25rem', text: '4X Large' },
              ].map((item) => (
                <div key={item.size} className="flex items-baseline gap-4">
                  <code className={`w-24 font-mono text-xs ${isDark ? 'text-navy-500' : 'text-navy-500'}`}>
                    text-{item.size}
                  </code>
                  <span className={`w-32 text-xs ${isDark ? 'text-navy-400' : 'text-navy-600'}`}>
                    {item.px} / {item.rem}
                  </span>
                  <span className={isDark ? 'text-white' : 'text-navy-900'} style={{ fontSize: item.rem }}>
                    {item.text}
                  </span>
                </div>
              ))}
            </div>
          </div>

          {/* Font Weights */}
          <div className={`rounded-2xl border p-6 ${isDark ? 'border-navy-800 bg-navy-900/50' : 'border-navy-200 bg-white'}`}>
            <h3 className={`mb-6 text-lg font-bold ${isDark ? 'text-white' : 'text-navy-900'}`}>
              Font Weights
            </h3>
            <div className="space-y-3">
              {[
                { weight: 'normal', value: '400', text: 'Normal Weight' },
                { weight: 'medium', value: '500', text: 'Medium Weight' },
                { weight: 'semibold', value: '600', text: 'Semibold Weight' },
                { weight: 'bold', value: '700', text: 'Bold Weight' },
                { weight: 'extrabold', value: '800', text: 'Extra Bold Weight' },
              ].map((item) => (
                <div key={item.weight} className="flex items-center gap-4">
                  <code className={`w-32 font-mono text-xs ${isDark ? 'text-navy-500' : 'text-navy-500'}`}>
                    font-{item.weight}
                  </code>
                  <span className={`text-lg ${isDark ? 'text-white' : 'text-navy-900'}`} style={{ fontWeight: item.value }}>
                    {item.text}
                  </span>
                </div>
              ))}
            </div>
          </div>
        </motion.section>
      )}

      {/* SPACING SECTION */}
      {activeSection === 'spacing' && (
        <motion.section
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          className="space-y-8"
        >
          <SectionHeader title="Spacing System" isDark={isDark} />
          <div className={`rounded-2xl border p-6 ${isDark ? 'border-navy-800 bg-navy-900/50' : 'border-navy-200 bg-white'}`}>
            <p className={`mb-6 text-sm ${isDark ? 'text-navy-400' : 'text-navy-600'}`}>
              4px base unit system for consistent spacing
            </p>
            <div className="space-y-4">
              {[
                { token: '0', value: '0px', rem: '0' },
                { token: '1', value: '4px', rem: '0.25rem' },
                { token: '2', value: '8px', rem: '0.5rem' },
                { token: '3', value: '12px', rem: '0.75rem' },
                { token: '4', value: '16px', rem: '1rem', note: 'Base unit' },
                { token: '5', value: '20px', rem: '1.25rem' },
                { token: '6', value: '24px', rem: '1.5rem' },
                { token: '8', value: '32px', rem: '2rem' },
                { token: '10', value: '40px', rem: '2.5rem' },
                { token: '12', value: '48px', rem: '3rem' },
              ].map((item) => (
                <div key={item.token} className="flex items-center gap-4">
                  <code className={`w-24 font-mono text-xs ${isDark ? 'text-navy-500' : 'text-navy-500'}`}>
                    space-{item.token}
                  </code>
                  <span className={`w-32 text-xs ${isDark ? 'text-navy-400' : 'text-navy-600'}`}>
                    {item.value} / {item.rem}
                  </span>
                  <div
                    className={`h-8 ${isDark ? 'bg-emerald-500' : 'bg-emerald-500'}`}
                    style={{ width: item.value }}
                  />
                  {item.note && (
                    <span className={`text-xs font-medium ${isDark ? 'text-emerald-400' : 'text-emerald-600'}`}>
                      {item.note}
                    </span>
                  )}
                </div>
              ))}
            </div>
          </div>
        </motion.section>
      )}

      {/* BORDER RADIUS SECTION */}
      {activeSection === 'radius' && (
        <motion.section
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          className="space-y-8"
        >
          <SectionHeader title="Border Radius" isDark={isDark} />
          <div className={`rounded-2xl border p-6 ${isDark ? 'border-navy-800 bg-navy-900/50' : 'border-navy-200 bg-white'}`}>
            <div className="grid grid-cols-2 gap-6">
              {[
                { token: 'sm', value: '6px', usage: 'Small elements' },
                { token: 'md', value: '8px', usage: 'Default' },
                { token: 'lg', value: '12px', usage: 'Medium elements' },
                { token: 'xl', value: '16px', usage: 'Buttons, inputs' },
                { token: '2xl', value: '24px', usage: 'Cards, modals' },
                { token: 'full', value: '9999px', usage: 'Pills, badges' },
              ].map((item) => (
                <div key={item.token} className="space-y-2">
                  <div className="flex items-center justify-between">
                    <code className={`font-mono text-xs ${isDark ? 'text-navy-400' : 'text-navy-600'}`}>
                      radius-{item.token}
                    </code>
                    <span className={`text-xs ${isDark ? 'text-navy-500' : 'text-navy-500'}`}>
                      {item.value}
                    </span>
                  </div>
                  <div
                    className={`h-24 w-full ${isDark ? 'bg-emerald-500' : 'bg-emerald-500'}`}
                    style={{ borderRadius: item.value }}
                  />
                  <p className={`text-xs ${isDark ? 'text-navy-400' : 'text-navy-600'}`}>
                    {item.usage}
                  </p>
                </div>
              ))}
            </div>
          </div>
        </motion.section>
      )}

      {/* SHADOWS SECTION */}
      {activeSection === 'shadows' && (
        <motion.section
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          className="space-y-8"
        >
          <SectionHeader title="Shadow System" isDark={isDark} />
          <div className={`space-y-6 rounded-2xl border p-6 ${isDark ? 'border-navy-800 bg-navy-900/50' : 'border-navy-200 bg-white'}`}>
            {[
              { name: 'xs', label: 'Extra Small' },
              { name: 'sm', label: 'Small' },
              { name: 'md', label: 'Medium' },
              { name: 'lg', label: 'Large' },
              { name: 'xl', label: 'Extra Large' },
              { name: '2xl', label: '2X Large' },
            ].map((shadow) => (
              <div key={shadow.name} className="space-y-2">
                <div className="flex items-center justify-between">
                  <code className={`font-mono text-xs ${isDark ? 'text-navy-400' : 'text-navy-600'}`}>
                    shadow-{shadow.name}
                  </code>
                  <span className={`text-xs ${isDark ? 'text-navy-500' : 'text-navy-500'}`}>
                    {shadow.label}
                  </span>
                </div>
                <div className={`rounded-xl p-8 ${isDark ? 'bg-navy-800' : 'bg-white'}`} style={{ boxShadow: `var(--shadow-${shadow.name})` }}>
                  <div className={`h-16 rounded-lg ${isDark ? 'bg-navy-700' : 'bg-navy-100'}`} />
                </div>
              </div>
            ))}

            {/* Glow Shadows */}
            <div className={`mt-8 border-t pt-6 ${isDark ? 'border-navy-800' : 'border-navy-200'}`}>
              <h4 className={`mb-4 text-sm font-semibold ${isDark ? 'text-white' : 'text-navy-900'}`}>
                Glow Effects
              </h4>
              <div className="grid grid-cols-3 gap-4">
                <div className={`rounded-xl p-6 shadow-lg shadow-emerald-500/40 ${isDark ? 'bg-navy-800' : 'bg-white'}`}>
                  <div className="h-16 rounded-lg bg-emerald-500" />
                  <p className={`mt-2 text-center text-xs ${isDark ? 'text-navy-400' : 'text-navy-600'}`}>
                    Emerald Glow
                  </p>
                </div>
                <div className={`rounded-xl p-6 shadow-lg shadow-blue-500/40 ${isDark ? 'bg-navy-800' : 'bg-white'}`}>
                  <div className="h-16 rounded-lg bg-blue-500" />
                  <p className={`mt-2 text-center text-xs ${isDark ? 'text-navy-400' : 'text-navy-600'}`}>
                    Blue Glow
                  </p>
                </div>
                <div className={`rounded-xl p-6 shadow-lg shadow-amber-500/40 ${isDark ? 'bg-navy-800' : 'bg-white'}`}>
                  <div className="h-16 rounded-lg bg-amber-500" />
                  <p className={`mt-2 text-center text-xs ${isDark ? 'text-navy-400' : 'text-navy-600'}`}>
                    Amber Glow
                  </p>
                </div>
              </div>
            </div>
          </div>
        </motion.section>
      )}

      {/* BUTTONS SECTION */}
      {activeSection === 'buttons' && (
        <motion.section
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          className="space-y-8"
        >
          <SectionHeader title="Button Components" isDark={isDark} />

          {/* Primary Buttons */}
          <div className={`rounded-2xl border p-6 ${isDark ? 'border-navy-800 bg-navy-900/50' : 'border-navy-200 bg-white'}`}>
            <h3 className={`mb-4 text-sm font-semibold ${isDark ? 'text-white' : 'text-navy-900'}`}>
              Primary Variant
            </h3>
            <div className="flex flex-wrap items-center gap-4">
              <button className="rounded-xl bg-gradient-to-r from-emerald-500 to-emerald-600 px-4 py-2 text-sm font-semibold text-white shadow-lg shadow-emerald-500/25 transition-all hover:from-emerald-600 hover:to-emerald-700 hover:shadow-xl">
                Small Button
              </button>
              <button className="rounded-xl bg-gradient-to-r from-emerald-500 to-emerald-600 px-6 py-3 text-base font-semibold text-white shadow-lg shadow-emerald-500/25 transition-all hover:from-emerald-600 hover:to-emerald-700 hover:shadow-xl">
                Medium Button
              </button>
              <button className="rounded-xl bg-gradient-to-r from-emerald-500 to-emerald-600 px-8 py-4 text-lg font-semibold text-white shadow-lg shadow-emerald-500/25 transition-all hover:from-emerald-600 hover:to-emerald-700 hover:shadow-xl">
                Large Button
              </button>
            </div>
          </div>

          {/* Secondary Buttons */}
          <div className={`rounded-2xl border p-6 ${isDark ? 'border-navy-800 bg-navy-900/50' : 'border-navy-200 bg-white'}`}>
            <h3 className={`mb-4 text-sm font-semibold ${isDark ? 'text-white' : 'text-navy-900'}`}>
              Secondary Variant
            </h3>
            <div className="flex flex-wrap items-center gap-4">
              <button className={`rounded-xl px-4 py-2 text-sm font-semibold transition-all hover:shadow-lg ${isDark ? 'bg-navy-700 text-white hover:bg-navy-600' : 'bg-navy-900 text-white hover:bg-navy-800'}`}>
                Small Button
              </button>
              <button className={`rounded-xl px-6 py-3 text-base font-semibold transition-all hover:shadow-lg ${isDark ? 'bg-navy-700 text-white hover:bg-navy-600' : 'bg-navy-900 text-white hover:bg-navy-800'}`}>
                Medium Button
              </button>
              <button className={`rounded-xl px-8 py-4 text-lg font-semibold transition-all hover:shadow-lg ${isDark ? 'bg-navy-700 text-white hover:bg-navy-600' : 'bg-navy-900 text-white hover:bg-navy-800'}`}>
                Large Button
              </button>
            </div>
          </div>

          {/* Outline Buttons */}
          <div className={`rounded-2xl border p-6 ${isDark ? 'border-navy-800 bg-navy-900/50' : 'border-navy-200 bg-white'}`}>
            <h3 className={`mb-4 text-sm font-semibold ${isDark ? 'text-white' : 'text-navy-900'}`}>
              Outline Variant
            </h3>
            <div className="flex flex-wrap items-center gap-4">
              <button className={`rounded-xl border-2 px-4 py-2 text-sm font-semibold transition-all ${isDark ? 'border-navy-600 text-navy-300 hover:border-navy-500 hover:bg-navy-800' : 'border-navy-300 text-navy-700 hover:border-navy-400 hover:bg-navy-50'}`}>
                Small Button
              </button>
              <button className={`rounded-xl border-2 px-6 py-3 text-base font-semibold transition-all ${isDark ? 'border-navy-600 text-navy-300 hover:border-navy-500 hover:bg-navy-800' : 'border-navy-300 text-navy-700 hover:border-navy-400 hover:bg-navy-50'}`}>
                Medium Button
              </button>
              <button className={`rounded-xl border-2 px-8 py-4 text-lg font-semibold transition-all ${isDark ? 'border-navy-600 text-navy-300 hover:border-navy-500 hover:bg-navy-800' : 'border-navy-300 text-navy-700 hover:border-navy-400 hover:bg-navy-50'}`}>
                Large Button
              </button>
            </div>
          </div>

          {/* Icon Buttons */}
          <div className={`rounded-2xl border p-6 ${isDark ? 'border-navy-800 bg-navy-900/50' : 'border-navy-200 bg-white'}`}>
            <h3 className={`mb-4 text-sm font-semibold ${isDark ? 'text-white' : 'text-navy-900'}`}>
              With Icons
            </h3>
            <div className="flex flex-wrap items-center gap-4">
              <button className="flex items-center gap-2 rounded-xl bg-gradient-to-r from-emerald-500 to-emerald-600 px-6 py-3 text-base font-semibold text-white shadow-lg shadow-emerald-500/25 transition-all hover:from-emerald-600 hover:to-emerald-700">
                <Download className="h-4 w-4" />
                Download
              </button>
              <button className="flex items-center gap-2 rounded-xl bg-gradient-to-r from-blue-500 to-blue-600 px-6 py-3 text-base font-semibold text-white shadow-lg shadow-blue-500/25 transition-all hover:from-blue-600 hover:to-blue-700">
                <Upload className="h-4 w-4" />
                Upload
              </button>
              <button className="flex items-center gap-2 rounded-xl bg-gradient-to-r from-amber-500 to-amber-600 px-6 py-3 text-base font-semibold text-white shadow-lg shadow-amber-500/25 transition-all hover:from-amber-600 hover:to-amber-700">
                <RefreshCw className="h-4 w-4" />
                Refresh
              </button>
            </div>
          </div>
        </motion.section>
      )}

      {/* INPUTS SECTION */}
      {activeSection === 'inputs' && (
        <motion.section
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          className="space-y-8"
        >
          <SectionHeader title="Input Components" isDark={isDark} />

          {/* Basic Input */}
          <div className={`rounded-2xl border p-6 ${isDark ? 'border-navy-800 bg-navy-900/50' : 'border-navy-200 bg-white'}`}>
            <h3 className={`mb-4 text-sm font-semibold ${isDark ? 'text-white' : 'text-navy-900'}`}>
              Text Input
            </h3>
            <div className="space-y-4">
              <div>
                <label className={`mb-2 block text-sm font-medium ${isDark ? 'text-navy-200' : 'text-navy-700'}`}>
                  Default State
                </label>
                <input
                  type="text"
                  placeholder="Enter text..."
                  className={`w-full rounded-xl border-2 px-4 py-3 transition-all focus:border-transparent focus:outline-none focus:ring-2 focus:ring-emerald-500 ${isDark ? 'border-navy-600 bg-navy-800 text-white placeholder-navy-400' : 'border-navy-200 bg-white text-navy-900 placeholder-navy-400'}`}
                />
              </div>
              <div>
                <label className={`mb-2 block text-sm font-medium ${isDark ? 'text-navy-200' : 'text-navy-700'}`}>
                  With Icon
                </label>
                <div className="relative">
                  <Search className={`absolute left-4 top-1/2 h-5 w-5 -trannavy-y-1/2 ${isDark ? 'text-navy-400' : 'text-navy-400'}`} />
                  <input
                    type="text"
                    placeholder="Search..."
                    className={`w-full rounded-xl border-2 py-3 pl-12 pr-4 transition-all focus:border-transparent focus:outline-none focus:ring-2 focus:ring-emerald-500 ${isDark ? 'border-navy-600 bg-navy-800 text-white placeholder-navy-400' : 'border-navy-200 bg-white text-navy-900 placeholder-navy-400'}`}
                  />
                </div>
              </div>
              <div>
                <label className={`mb-2 block text-sm font-medium ${isDark ? 'text-red-400' : 'text-red-600'}`}>
                  Error State
                </label>
                <input
                  type="text"
                  placeholder="Error..."
                  className={`w-full rounded-xl border-2 px-4 py-3 transition-all focus:border-red-500 focus:outline-none focus:ring-2 focus:ring-red-500 ${isDark ? 'border-red-500/50 bg-navy-800 text-white' : 'border-red-500 bg-white text-navy-900'}`}
                />
                <p className={`mt-1 text-xs ${isDark ? 'text-red-400' : 'text-red-600'}`}>
                  This field is required
                </p>
              </div>
              <div>
                <label className={`mb-2 block text-sm font-medium ${isDark ? 'text-navy-400' : 'text-navy-500'}`}>
                  Disabled State
                </label>
                <input
                  type="text"
                  placeholder="Disabled..."
                  disabled
                  className={`w-full cursor-not-allowed rounded-xl border-2 px-4 py-3 ${isDark ? 'border-navy-700 bg-navy-800/50 text-navy-500' : 'border-navy-200 bg-navy-100 text-navy-400'}`}
                />
              </div>
            </div>
          </div>
        </motion.section>
      )}

      {/* BADGES SECTION */}
      {activeSection === 'badges' && (
        <motion.section
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          className="space-y-8"
        >
          <SectionHeader title="Badge Components" isDark={isDark} />

          <div className={`rounded-2xl border p-6 ${isDark ? 'border-navy-800 bg-navy-900/50' : 'border-navy-200 bg-white'}`}>
            <div className="space-y-6">
              {/* Status Badges */}
              <div>
                <h3 className={`mb-4 text-sm font-semibold ${isDark ? 'text-white' : 'text-navy-900'}`}>
                  Status Badges
                </h3>
                <div className="flex flex-wrap gap-3">
                  <span className={`inline-flex items-center gap-1.5 rounded-full px-3 py-1 text-xs font-medium ${isDark ? 'bg-emerald-500/20 text-emerald-400' : 'bg-emerald-100 text-emerald-700'}`}>
                    <Check className="h-3 w-3" />
                    Success
                  </span>
                  <span className={`inline-flex items-center gap-1.5 rounded-full px-3 py-1 text-xs font-medium ${isDark ? 'bg-amber-500/20 text-amber-400' : 'bg-amber-100 text-amber-700'}`}>
                    <AlertTriangle className="h-3 w-3" />
                    Warning
                  </span>
                  <span className={`inline-flex items-center gap-1.5 rounded-full px-3 py-1 text-xs font-medium ${isDark ? 'bg-red-500/20 text-red-400' : 'bg-red-100 text-red-700'}`}>
                    <AlertCircle className="h-3 w-3" />
                    Error
                  </span>
                  <span className={`inline-flex items-center gap-1.5 rounded-full px-3 py-1 text-xs font-medium ${isDark ? 'bg-blue-500/20 text-blue-400' : 'bg-blue-100 text-blue-700'}`}>
                    <Info className="h-3 w-3" />
                    Info
                  </span>
                </div>
              </div>

              {/* Certificate Badges */}
              <div>
                <h3 className={`mb-4 text-sm font-semibold ${isDark ? 'text-white' : 'text-navy-900'}`}>
                  Certificate Badges
                </h3>
                <div className="flex flex-wrap gap-3">
                  <span className={`inline-flex items-center gap-1.5 rounded-full border px-4 py-2 text-sm font-semibold ${isDark ? 'border-blue-500/50 bg-blue-500/20 text-blue-400' : 'border-blue-200 bg-blue-100 text-blue-700'}`}>
                    <Leaf className="h-4 w-4" />
                    EUA Certificate
                  </span>
                  <span className={`inline-flex items-center gap-1.5 rounded-full border px-4 py-2 text-sm font-semibold ${isDark ? 'border-amber-500/50 bg-amber-500/20 text-amber-400' : 'border-amber-200 bg-amber-100 text-amber-700'}`}>
                    <Wind className="h-4 w-4" />
                    CEA Certificate
                  </span>
                </div>
              </div>

              {/* Trading Badges */}
              <div>
                <h3 className={`mb-4 text-sm font-semibold ${isDark ? 'text-white' : 'text-navy-900'}`}>
                  Trading Badges
                </h3>
                <div className="flex flex-wrap gap-3">
                  <span className={`inline-flex items-center gap-1.5 rounded-full px-4 py-2 text-sm font-bold ${isDark ? 'bg-emerald-500/20 text-emerald-400' : 'bg-emerald-100 text-emerald-700'}`}>
                    <TrendingUp className="h-4 w-4" />
                    BID €99.50
                  </span>
                  <span className={`inline-flex items-center gap-1.5 rounded-full px-4 py-2 text-sm font-bold ${isDark ? 'bg-red-500/20 text-red-400' : 'bg-red-100 text-red-700'}`}>
                    <TrendingDown className="h-4 w-4" />
                    ASK €101.25
                  </span>
                </div>
              </div>

              {/* Count Badges */}
              <div>
                <h3 className={`mb-4 text-sm font-semibold ${isDark ? 'text-white' : 'text-navy-900'}`}>
                  Count Badges
                </h3>
                <div className="flex flex-wrap items-center gap-4">
                  <div className="relative">
                    <Bell className={`h-6 w-6 ${isDark ? 'text-navy-400' : 'text-navy-600'}`} />
                    <span className="absolute -right-1 -top-1 flex h-5 w-5 items-center justify-center rounded-full bg-red-500 text-[10px] font-bold text-white">
                      3
                    </span>
                  </div>
                  <div className="relative">
                    <Settings className={`h-6 w-6 ${isDark ? 'text-navy-400' : 'text-navy-600'}`} />
                    <span className="absolute -right-1 -top-1 flex h-5 w-5 items-center justify-center rounded-full bg-emerald-500 text-[10px] font-bold text-white">
                      12
                    </span>
                  </div>
                </div>
              </div>
            </div>
          </div>
        </motion.section>
      )}

      {/* CARDS SECTION */}
      {activeSection === 'cards' && (
        <motion.section
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          className="space-y-8"
        >
          <SectionHeader title="Card Components" isDark={isDark} />

          {/* Default Card */}
          <div>
            <h3 className={`mb-4 text-sm font-semibold ${isDark ? 'text-white' : 'text-navy-900'}`}>
              Default Card
            </h3>
            <div className={`rounded-2xl border p-6 shadow-lg transition-all hover:shadow-xl ${isDark ? 'border-navy-700 bg-navy-800' : 'border-navy-200 bg-white'}`}>
              <div className="flex items-start gap-4">
                <div className={`rounded-xl p-3 ${isDark ? 'bg-emerald-500/20' : 'bg-emerald-100'}`}>
                  <Activity className={`h-6 w-6 ${isDark ? 'text-emerald-400' : 'text-emerald-600'}`} />
                </div>
                <div className="flex-1">
                  <h4 className={`text-lg font-bold ${isDark ? 'text-white' : 'text-navy-900'}`}>
                    Card Title
                  </h4>
                  <p className={`mt-1 text-sm ${isDark ? 'text-navy-400' : 'text-navy-600'}`}>
                    This is a default card with border, background, and shadow. It has hover effects.
                  </p>
                  <div className="mt-4 flex gap-2">
                    <button className="rounded-lg bg-emerald-500 px-4 py-2 text-sm font-semibold text-white transition-colors hover:bg-emerald-600">
                      Action
                    </button>
                    <button className={`rounded-lg border px-4 py-2 text-sm font-semibold transition-colors ${isDark ? 'border-navy-600 text-navy-300 hover:bg-navy-700' : 'border-navy-300 text-navy-700 hover:bg-navy-50'}`}>
                      Cancel
                    </button>
                  </div>
                </div>
              </div>
            </div>
          </div>

          {/* Glass Card */}
          <div>
            <h3 className={`mb-4 text-sm font-semibold ${isDark ? 'text-white' : 'text-navy-900'}`}>
              Glass Card (Glassmorphism)
            </h3>
            <div className={`rounded-2xl border p-6 shadow-lg backdrop-blur-lg ${isDark ? 'border-navy-700/50 bg-navy-800/80' : 'border-white/20 bg-white/80'}`}>
              <div className="flex items-start gap-4">
                <div className={`rounded-xl p-3 ${isDark ? 'bg-blue-500/20' : 'bg-blue-100'}`}>
                  <BarChart3 className={`h-6 w-6 ${isDark ? 'text-blue-400' : 'text-blue-600'}`} />
                </div>
                <div className="flex-1">
                  <h4 className={`text-lg font-bold ${isDark ? 'text-white' : 'text-navy-900'}`}>
                    Glass Card
                  </h4>
                  <p className={`mt-1 text-sm ${isDark ? 'text-navy-400' : 'text-navy-600'}`}>
                    Frosted glass effect with backdrop blur for modern, elevated UI elements.
                  </p>
                </div>
              </div>
            </div>
          </div>

          {/* Stat Cards */}
          <div>
            <h3 className={`mb-4 text-sm font-semibold ${isDark ? 'text-white' : 'text-navy-900'}`}>
              Stat Cards
            </h3>
            <div className="grid grid-cols-2 gap-4">
              <div className={`rounded-2xl border p-6 ${isDark ? 'border-navy-700 bg-navy-800' : 'border-navy-200 bg-white'}`}>
                <div className="flex items-start justify-between">
                  <div>
                    <p className={`text-sm font-medium ${isDark ? 'text-navy-400' : 'text-navy-600'}`}>
                      Total Revenue
                    </p>
                    <p className={`mt-2 font-mono text-3xl font-bold ${isDark ? 'text-white' : 'text-navy-900'}`}>
                      €12,543
                    </p>
                    <div className="mt-2 flex items-center gap-1 text-sm font-semibold text-emerald-500">
                      <TrendingUp className="h-4 w-4" />
                      +12.5%
                    </div>
                  </div>
                  <div className={`rounded-xl p-3 ${isDark ? 'bg-emerald-500/20' : 'bg-emerald-100'}`}>
                    <Euro className={`h-6 w-6 ${isDark ? 'text-emerald-400' : 'text-emerald-600'}`} />
                  </div>
                </div>
              </div>
              <div className={`rounded-2xl border p-6 ${isDark ? 'border-navy-700 bg-navy-800' : 'border-navy-200 bg-white'}`}>
                <div className="flex items-start justify-between">
                  <div>
                    <p className={`text-sm font-medium ${isDark ? 'text-navy-400' : 'text-navy-600'}`}>
                      Active Orders
                    </p>
                    <p className={`mt-2 font-mono text-3xl font-bold ${isDark ? 'text-white' : 'text-navy-900'}`}>
                      1,234
                    </p>
                    <div className="mt-2 flex items-center gap-1 text-sm font-semibold text-red-500">
                      <TrendingDown className="h-4 w-4" />
                      -3.2%
                    </div>
                  </div>
                  <div className={`rounded-xl p-3 ${isDark ? 'bg-blue-500/20' : 'bg-blue-100'}`}>
                    <Activity className={`h-6 w-6 ${isDark ? 'text-blue-400' : 'text-blue-600'}`} />
                  </div>
                </div>
              </div>
            </div>
          </div>
        </motion.section>
      )}

      {/* TABLES SECTION */}
      {activeSection === 'tables' && (
        <motion.section
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          className="space-y-8"
        >
          <SectionHeader title="Data Table" isDark={isDark} />

          <div className={`overflow-hidden rounded-2xl border ${isDark ? 'border-navy-700 bg-navy-800' : 'border-navy-200 bg-white'}`}>
            <table className="w-full">
              <thead className={`border-b ${isDark ? 'border-navy-700 bg-navy-900/50' : 'border-navy-200 bg-navy-50'}`}>
                <tr>
                  <th className={`px-6 py-4 text-left text-xs font-semibold uppercase tracking-wider ${isDark ? 'text-navy-400' : 'text-navy-600'}`}>
                    Certificate
                  </th>
                  <th className={`px-6 py-4 text-right text-xs font-semibold uppercase tracking-wider ${isDark ? 'text-navy-400' : 'text-navy-600'}`}>
                    Price
                  </th>
                  <th className={`px-6 py-4 text-right text-xs font-semibold uppercase tracking-wider ${isDark ? 'text-navy-400' : 'text-navy-600'}`}>
                    Change
                  </th>
                  <th className={`px-6 py-4 text-right text-xs font-semibold uppercase tracking-wider ${isDark ? 'text-navy-400' : 'text-navy-600'}`}>
                    Volume
                  </th>
                  <th className={`px-6 py-4 text-center text-xs font-semibold uppercase tracking-wider ${isDark ? 'text-navy-400' : 'text-navy-600'}`}>
                    Status
                  </th>
                </tr>
              </thead>
              <tbody className={`divide-y ${isDark ? 'divide-navy-700' : 'divide-navy-200'}`}>
                <tr className={`transition-colors ${isDark ? 'hover:bg-navy-700/50' : 'hover:bg-navy-50'}`}>
                  <td className="px-6 py-4">
                    <div className="flex items-center gap-3">
                      <div className={`rounded-lg p-2 ${isDark ? 'bg-blue-500/20' : 'bg-blue-100'}`}>
                        <Leaf className={`h-4 w-4 ${isDark ? 'text-blue-400' : 'text-blue-600'}`} />
                      </div>
                      <div>
                        <div className={`text-sm font-semibold ${isDark ? 'text-white' : 'text-navy-900'}`}>
                          EUA
                        </div>
                        <div className={`text-xs ${isDark ? 'text-navy-400' : 'text-navy-600'}`}>
                          EU Allowance
                        </div>
                      </div>
                    </div>
                  </td>
                  <td className={`px-6 py-4 text-right font-mono text-sm font-semibold ${isDark ? 'text-white' : 'text-navy-900'}`}>
                    €99.50
                  </td>
                  <td className="px-6 py-4 text-right">
                    <div className="flex items-center justify-end gap-1 text-sm font-semibold text-emerald-500">
                      <TrendingUp className="h-4 w-4" />
                      +2.5%
                    </div>
                  </td>
                  <td className={`px-6 py-4 text-right font-mono text-sm ${isDark ? 'text-navy-300' : 'text-navy-700'}`}>
                    12,543
                  </td>
                  <td className="px-6 py-4">
                    <div className="flex justify-center">
                      <span className={`inline-flex items-center gap-1 rounded-full px-2.5 py-1 text-xs font-medium ${isDark ? 'bg-emerald-500/20 text-emerald-400' : 'bg-emerald-100 text-emerald-700'}`}>
                        <Check className="h-3 w-3" />
                        Active
                      </span>
                    </div>
                  </td>
                </tr>
                <tr className={`transition-colors ${isDark ? 'hover:bg-navy-700/50' : 'hover:bg-navy-50'}`}>
                  <td className="px-6 py-4">
                    <div className="flex items-center gap-3">
                      <div className={`rounded-lg p-2 ${isDark ? 'bg-amber-500/20' : 'bg-amber-100'}`}>
                        <Wind className={`h-4 w-4 ${isDark ? 'text-amber-400' : 'text-amber-600'}`} />
                      </div>
                      <div>
                        <div className={`text-sm font-semibold ${isDark ? 'text-white' : 'text-navy-900'}`}>
                          CEA
                        </div>
                        <div className={`text-xs ${isDark ? 'text-navy-400' : 'text-navy-600'}`}>
                          China Allowance
                        </div>
                      </div>
                    </div>
                  </td>
                  <td className={`px-6 py-4 text-right font-mono text-sm font-semibold ${isDark ? 'text-white' : 'text-navy-900'}`}>
                    €47.25
                  </td>
                  <td className="px-6 py-4 text-right">
                    <div className="flex items-center justify-end gap-1 text-sm font-semibold text-red-500">
                      <TrendingDown className="h-4 w-4" />
                      -1.2%
                    </div>
                  </td>
                  <td className={`px-6 py-4 text-right font-mono text-sm ${isDark ? 'text-navy-300' : 'text-navy-700'}`}>
                    8,921
                  </td>
                  <td className="px-6 py-4">
                    <div className="flex justify-center">
                      <span className={`inline-flex items-center gap-1 rounded-full px-2.5 py-1 text-xs font-medium ${isDark ? 'bg-amber-500/20 text-amber-400' : 'bg-amber-100 text-amber-700'}`}>
                        <AlertTriangle className="h-3 w-3" />
                        Pending
                      </span>
                    </div>
                  </td>
                </tr>
              </tbody>
            </table>
          </div>
        </motion.section>
      )}

      {/* TRADING UI SECTION */}
      {activeSection === 'trading' && (
        <motion.section
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          className="space-y-8"
        >
          <SectionHeader title="Trading UI Components" isDark={isDark} />

          {/* Order Book */}
          <div className={`rounded-2xl border p-6 ${isDark ? 'border-navy-700 bg-navy-800' : 'border-navy-200 bg-white'}`}>
            <h3 className={`mb-4 text-sm font-semibold ${isDark ? 'text-white' : 'text-navy-900'}`}>
              Order Book Rows
            </h3>
            <div className="space-y-2">
              {/* Bid Row */}
              <div className={`rounded-lg p-3 transition-colors ${isDark ? 'hover:bg-emerald-500/10' : 'hover:bg-emerald-50'}`}>
                <div className="flex items-center justify-between">
                  <span className={`text-sm font-semibold ${isDark ? 'text-emerald-400' : 'text-emerald-600'}`}>
                    €99.50
                  </span>
                  <span className={`font-mono text-sm ${isDark ? 'text-navy-300' : 'text-navy-700'}`}>
                    1,234
                  </span>
                  <span className={`text-xs ${isDark ? 'text-navy-400' : 'text-navy-600'}`}>
                    5 orders
                  </span>
                </div>
              </div>
              <div className={`rounded-lg p-3 transition-colors ${isDark ? 'hover:bg-emerald-500/10' : 'hover:bg-emerald-50'}`}>
                <div className="flex items-center justify-between">
                  <span className={`text-sm font-semibold ${isDark ? 'text-emerald-400' : 'text-emerald-600'}`}>
                    €99.45
                  </span>
                  <span className={`font-mono text-sm ${isDark ? 'text-navy-300' : 'text-navy-700'}`}>
                    2,567
                  </span>
                  <span className={`text-xs ${isDark ? 'text-navy-400' : 'text-navy-600'}`}>
                    8 orders
                  </span>
                </div>
              </div>

              {/* Spread Indicator */}
              <div className={`my-4 border-t border-b py-3 ${isDark ? 'border-navy-700' : 'border-navy-200'}`}>
                <div className="flex items-center justify-center gap-2">
                  <span className={`text-xs font-medium ${isDark ? 'text-navy-400' : 'text-navy-600'}`}>
                    Spread:
                  </span>
                  <span className={`font-mono text-sm font-bold ${isDark ? 'text-white' : 'text-navy-900'}`}>
                    €0.10
                  </span>
                </div>
              </div>

              {/* Ask Row */}
              <div className={`rounded-lg p-3 transition-colors ${isDark ? 'hover:bg-red-500/10' : 'hover:bg-red-50'}`}>
                <div className="flex items-center justify-between">
                  <span className={`text-sm font-semibold ${isDark ? 'text-red-400' : 'text-red-600'}`}>
                    €99.55
                  </span>
                  <span className={`font-mono text-sm ${isDark ? 'text-navy-300' : 'text-navy-700'}`}>
                    3,421
                  </span>
                  <span className={`text-xs ${isDark ? 'text-navy-400' : 'text-navy-600'}`}>
                    6 orders
                  </span>
                </div>
              </div>
              <div className={`rounded-lg p-3 transition-colors ${isDark ? 'hover:bg-red-500/10' : 'hover:bg-red-50'}`}>
                <div className="flex items-center justify-between">
                  <span className={`text-sm font-semibold ${isDark ? 'text-red-400' : 'text-red-600'}`}>
                    €99.60
                  </span>
                  <span className={`font-mono text-sm ${isDark ? 'text-navy-300' : 'text-navy-700'}`}>
                    1,876
                  </span>
                  <span className={`text-xs ${isDark ? 'text-navy-400' : 'text-navy-600'}`}>
                    4 orders
                  </span>
                </div>
              </div>
            </div>
          </div>

          {/* Price Movement */}
          <div className={`rounded-2xl border p-6 ${isDark ? 'border-navy-700 bg-navy-800' : 'border-navy-200 bg-white'}`}>
            <h3 className={`mb-4 text-sm font-semibold ${isDark ? 'text-white' : 'text-navy-900'}`}>
              Price Movement Indicators
            </h3>
            <div className="grid grid-cols-2 gap-4">
              <div className={`rounded-xl p-4 ${isDark ? 'bg-emerald-500/10 border border-emerald-500/20' : 'bg-emerald-50 border border-emerald-200'}`}>
                <div className="flex items-center gap-2">
                  <TrendingUp className={`h-5 w-5 ${isDark ? 'text-emerald-400' : 'text-emerald-600'}`} />
                  <span className={`text-sm font-medium ${isDark ? 'text-emerald-400' : 'text-emerald-700'}`}>
                    Positive
                  </span>
                </div>
                <p className={`mt-2 font-mono text-2xl font-bold ${isDark ? 'text-emerald-400' : 'text-emerald-600'}`}>
                  +€2.50
                </p>
                <p className={`text-xs ${isDark ? 'text-emerald-400/70' : 'text-emerald-600/70'}`}>
                  +2.57% today
                </p>
              </div>
              <div className={`rounded-xl p-4 ${isDark ? 'bg-red-500/10 border border-red-500/20' : 'bg-red-50 border border-red-200'}`}>
                <div className="flex items-center gap-2">
                  <TrendingDown className={`h-5 w-5 ${isDark ? 'text-red-400' : 'text-red-600'}`} />
                  <span className={`text-sm font-medium ${isDark ? 'text-red-400' : 'text-red-700'}`}>
                    Negative
                  </span>
                </div>
                <p className={`mt-2 font-mono text-2xl font-bold ${isDark ? 'text-red-400' : 'text-red-600'}`}>
                  -€1.25
                </p>
                <p className={`text-xs ${isDark ? 'text-red-400/70' : 'text-red-600/70'}`}>
                  -1.28% today
                </p>
              </div>
            </div>
          </div>
        </motion.section>
      )}

      {/* ICONS SECTION */}
      {activeSection === 'icons' && (
        <motion.section
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          className="space-y-8"
        >
          <SectionHeader title="Icon Library" isDark={isDark} />

          <div className={`rounded-2xl border p-6 ${isDark ? 'border-navy-700 bg-navy-800' : 'border-navy-200 bg-white'}`}>
            <p className={`mb-6 text-sm ${isDark ? 'text-navy-400' : 'text-navy-600'}`}>
              Using Lucide React icon library
            </p>
            <div className="grid grid-cols-6 gap-4">
              {[
                { Icon: User, name: 'User' },
                { Icon: Settings, name: 'Settings' },
                { Icon: Bell, name: 'Bell' },
                { Icon: Search, name: 'Search' },
                { Icon: Filter, name: 'Filter' },
                { Icon: Download, name: 'Download' },
                { Icon: Upload, name: 'Upload' },
                { Icon: RefreshCw, name: 'Refresh' },
                { Icon: TrendingUp, name: 'Up' },
                { Icon: TrendingDown, name: 'Down' },
                { Icon: BarChart3, name: 'Chart' },
                { Icon: Activity, name: 'Activity' },
                { Icon: Check, name: 'Check' },
                { Icon: AlertCircle, name: 'Alert' },
                { Icon: Info, name: 'Info' },
                { Icon: Leaf, name: 'Leaf' },
                { Icon: Wind, name: 'Wind' },
                { Icon: Euro, name: 'Euro' },
              ].map(({ Icon, name }) => (
                <div key={name} className={`flex flex-col items-center gap-2 rounded-xl p-4 transition-colors ${isDark ? 'hover:bg-navy-700' : 'hover:bg-navy-50'}`}>
                  <Icon className={`h-6 w-6 ${isDark ? 'text-navy-300' : 'text-navy-700'}`} />
                  <span className={`text-xs ${isDark ? 'text-navy-400' : 'text-navy-600'}`}>
                    {name}
                  </span>
                </div>
              ))}
            </div>
          </div>
        </motion.section>
      )}

      {/* ANIMATIONS SECTION */}
      {activeSection === 'animations' && (
        <motion.section
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          className="space-y-8"
        >
          <SectionHeader title="Animation Patterns" isDark={isDark} />

          {/* Fade In */}
          <div className={`rounded-2xl border p-6 ${isDark ? 'border-navy-700 bg-navy-800' : 'border-navy-200 bg-white'}`}>
            <h3 className={`mb-4 text-sm font-semibold ${isDark ? 'text-white' : 'text-navy-900'}`}>
              Fade In
            </h3>
            <motion.div
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              transition={{ duration: 0.5, repeat: Infinity, repeatDelay: 1 }}
              className={`rounded-xl p-6 ${isDark ? 'bg-navy-700' : 'bg-navy-100'}`}
            >
              <p className={`text-sm ${isDark ? 'text-navy-300' : 'text-navy-700'}`}>
                Fading in and out continuously
              </p>
            </motion.div>
          </div>

          {/* Slide Up */}
          <div className={`rounded-2xl border p-6 ${isDark ? 'border-navy-700 bg-navy-800' : 'border-navy-200 bg-white'}`}>
            <h3 className={`mb-4 text-sm font-semibold ${isDark ? 'text-white' : 'text-navy-900'}`}>
              Slide Up
            </h3>
            <motion.div
              initial={{ opacity: 0, y: 20 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ duration: 0.5, repeat: Infinity, repeatDelay: 1 }}
              className={`rounded-xl p-6 ${isDark ? 'bg-navy-700' : 'bg-navy-100'}`}
            >
              <p className={`text-sm ${isDark ? 'text-navy-300' : 'text-navy-700'}`}>
                Sliding up from bottom
              </p>
            </motion.div>
          </div>

          {/* Scale In */}
          <div className={`rounded-2xl border p-6 ${isDark ? 'border-navy-700 bg-navy-800' : 'border-navy-200 bg-white'}`}>
            <h3 className={`mb-4 text-sm font-semibold ${isDark ? 'text-white' : 'text-navy-900'}`}>
              Scale In
            </h3>
            <motion.div
              initial={{ opacity: 0, scale: 0.9 }}
              animate={{ opacity: 1, scale: 1 }}
              transition={{ duration: 0.3, repeat: Infinity, repeatDelay: 1 }}
              className={`rounded-xl p-6 ${isDark ? 'bg-navy-700' : 'bg-navy-100'}`}
            >
              <p className={`text-sm ${isDark ? 'text-navy-300' : 'text-navy-700'}`}>
                Scaling from 90% to 100%
              </p>
            </motion.div>
          </div>

          {/* Pulse */}
          <div className={`rounded-2xl border p-6 ${isDark ? 'border-navy-700 bg-navy-800' : 'border-navy-200 bg-white'}`}>
            <h3 className={`mb-4 text-sm font-semibold ${isDark ? 'text-white' : 'text-navy-900'}`}>
              Pulse (CSS)
            </h3>
            <div className="flex items-center gap-4">
              <div className={`h-12 w-12 animate-pulse rounded-full ${isDark ? 'bg-emerald-500' : 'bg-emerald-500'}`} />
              <div className={`h-12 w-12 animate-pulse rounded-full ${isDark ? 'bg-blue-500' : 'bg-blue-500'}`} style={{ animationDelay: '150ms' }} />
              <div className={`h-12 w-12 animate-pulse rounded-full ${isDark ? 'bg-amber-500' : 'bg-amber-500'}`} style={{ animationDelay: '300ms' }} />
            </div>
          </div>

          {/* Spin */}
          <div className={`rounded-2xl border p-6 ${isDark ? 'border-navy-700 bg-navy-800' : 'border-navy-200 bg-white'}`}>
            <h3 className={`mb-4 text-sm font-semibold ${isDark ? 'text-white' : 'text-navy-900'}`}>
              Spin (Loading)
            </h3>
            <RefreshCw className={`h-8 w-8 animate-spin ${isDark ? 'text-emerald-400' : 'text-emerald-500'}`} />
          </div>
        </motion.section>
      )}
    </>
  );
}

// Helper Components
function SectionHeader({ title, isDark }: { title: string; isDark: boolean }) {
  return (
    <div className="mb-6">
      <h2 className={`text-2xl font-bold ${isDark ? 'text-white' : 'text-navy-900'}`}>
        {title}
      </h2>
      <div className={`mt-2 h-1 w-20 rounded-full ${isDark ? 'bg-emerald-500' : 'bg-emerald-500'}`} />
    </div>
  );
}

function ColorGroup({
  title,
  colors,
  isDark,
}: {
  title: string;
  colors: Array<{ name: string; var: string; class: string; icon?: React.ReactNode }>;
  isDark: boolean;
}) {
  return (
    <div className={`rounded-2xl border p-6 ${isDark ? 'border-navy-800 bg-navy-900/50' : 'border-navy-200 bg-white'}`}>
      <h3 className={`mb-4 text-sm font-semibold ${isDark ? 'text-white' : 'text-navy-900'}`}>
        {title}
      </h3>
      <div className="space-y-3">
        {colors.map((color) => (
          <div key={color.name} className="flex items-center gap-3">
            <div className={`relative h-12 w-12 overflow-hidden rounded-xl ${color.class} shadow-md`}>
              {color.icon && (
                <div className="flex h-full w-full items-center justify-center text-white">
                  {color.icon}
                </div>
              )}
            </div>
            <div className="flex-1">
              <p className={`text-sm font-medium ${isDark ? 'text-navy-200' : 'text-navy-900'}`}>
                {color.name}
              </p>
              <code className={`text-xs font-mono ${isDark ? 'text-navy-400' : 'text-navy-600'}`}>
                var({color.var})
              </code>
            </div>
            <button className={`rounded-lg p-2 transition-colors ${isDark ? 'hover:bg-navy-700' : 'hover:bg-navy-100'}`}>
              <Copy className={`h-4 w-4 ${isDark ? 'text-navy-400' : 'text-navy-500'}`} />
            </button>
          </div>
        ))}
      </div>
    </div>
  );
}
