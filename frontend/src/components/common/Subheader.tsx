import { type ReactNode } from 'react';
import { Link } from 'react-router-dom';
import { cn } from '../../utils';

interface SubheaderProps {
  /** Icon element to display in the icon container */
  icon: ReactNode;
  /** Main title text */
  title: string;
  /** Description/subtitle text */
  description: string;
  /** Page-specific content to display on the right side (stats, buttons, etc.) */
  children?: ReactNode;
  /** Optional additional className for the container */
  className?: string;
  /** Optional link URL - when provided, title and icon become clickable */
  to?: string;
  /** Icon container background color class (default: bg-emerald-500/20) */
  iconBg?: string;
  /** When false, do not render the spacer (use when SubSubHeader follows immediately to avoid gap) */
  renderSpacer?: boolean;
}

/**
 * Subheader Component
 * 
 * A reusable page subheader component with consistent styling.
 * Displays an icon, title, description, and optional right-side content.
 * Appears under the header on every page.
 * 
 * @example
 * ```tsx
 * <Subheader
 *   icon={<LayoutDashboard className="w-5 h-5 text-emerald-500" />}
 *   title="Portfolio Dashboard"
 *   description="Nihao Group"
 *   iconBg="bg-emerald-500/20"
 * >
 *   <button className="p-2.5 rounded-lg bg-navy-700 hover:bg-navy-600 text-navy-400">
 *     <RefreshCw className="w-4 h-4" />
 *   </button>
 * </Subheader>
 * ```
 */
export function Subheader({
  icon,
  title,
  description,
  children,
  className,
  to,
  iconBg = 'bg-emerald-500/20',
  renderSpacer = true,
}: SubheaderProps) {
  const content = (
    <>
      <div className={cn('w-10 h-10 rounded-xl flex items-center justify-center', iconBg)}>
        {icon}
      </div>
      <div>
        <h1 className="section-heading text-white">{title}</h1>
        <p className="text-sm text-navy-400">{description}</p>
      </div>
    </>
  );

  return (
    <>
      <div className={cn('subheader-bar', className)}>
        <div className="max-w-7xl mx-auto">
          <div className="flex flex-col lg:flex-row lg:items-center lg:justify-between gap-4">
            {/* Left side: Icon, Title, Description */}
            {to ? (
              <Link
                to={to}
                className="flex items-center gap-3 hover:opacity-80 transition-opacity cursor-pointer"
              >
                {content}
              </Link>
            ) : (
              <div className="flex items-center gap-3">
                {content}
              </div>
            )}

            {/* Right side: Page-specific content */}
            {children && (
              <div className="flex items-center gap-6 text-sm">
                {children}
              </div>
            )}
          </div>
        </div>
      </div>
      {renderSpacer && <div className="subheader-bar-spacer" aria-hidden="true" />}
    </>
  );
}
