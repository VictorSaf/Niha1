import { motion } from 'framer-motion';

/** Login and NDA success background animations. Uses design tokens where applicable. */

export function GrowingTree() {
  return (
    <motion.div
      className="relative w-full pointer-events-none"
      initial={{ opacity: 0 }}
      animate={{ opacity: 0.55 }}
      transition={{ duration: 3 }}
    >
      {/* Extra top padding in viewBox so crown + strokes aren’t clipped when scaled */}
      <svg
        viewBox="0 -80 200 380"
        className="block h-auto w-full max-h-[min(78vh,680px)]"
        preserveAspectRatio="xMidYMax meet"
      >
        {/* SVG stroke exception: dark-only login – explicit brown for trunk/branches */}
        <motion.path
          d="M100 300 Q100 250 95 200 Q90 150 100 100"
          stroke="rgb(120, 53, 15)"
          strokeWidth="12"
          fill="none"
          strokeLinecap="round"
          initial={{ pathLength: 0 }}
          animate={{ pathLength: 1 }}
          transition={{ duration: 8, ease: 'easeOut' }}
        />
        <motion.path
          d="M100 180 Q130 160 150 140"
          stroke="rgb(120, 53, 15)"
          strokeWidth="6"
          fill="none"
          strokeLinecap="round"
          initial={{ pathLength: 0 }}
          animate={{ pathLength: 1 }}
          transition={{ duration: 3, delay: 3, ease: 'easeOut' }}
        />
        <motion.path
          d="M100 150 Q60 130 40 100"
          stroke="rgb(120, 53, 15)"
          strokeWidth="6"
          fill="none"
          strokeLinecap="round"
          initial={{ pathLength: 0 }}
          animate={{ pathLength: 1 }}
          transition={{ duration: 3, delay: 4, ease: 'easeOut' }}
        />
        <motion.path
          d="M100 120 Q140 100 160 70"
          stroke="rgb(120, 53, 15)"
          strokeWidth="5"
          fill="none"
          strokeLinecap="round"
          initial={{ pathLength: 0 }}
          animate={{ pathLength: 1 }}
          transition={{ duration: 2, delay: 5, ease: 'easeOut' }}
        />
        {[
          { cx: 150, cy: 130, r: 30, delay: 6 },
          { cx: 40, cy: 90, r: 35, delay: 6.5 },
          { cx: 160, cy: 60, r: 28, delay: 7 },
          { cx: 100, cy: 80, r: 40, delay: 7.5 },
          { cx: 70, cy: 60, r: 32, delay: 8 },
          { cx: 130, cy: 40, r: 30, delay: 8.5 },
          { cx: 100, cy: 30, r: 35, delay: 9 },
        ].map((leaf, i) => (
          <motion.circle
            key={i}
            cx={leaf.cx}
            cy={leaf.cy}
            r={leaf.r}
            fill="rgb(16, 185, 129)"
            fillOpacity="0.5"
            initial={{ scale: 0, opacity: 0 }}
            animate={{ scale: 1, opacity: 0.5 }}
            transition={{ duration: 2, delay: leaf.delay, ease: 'easeOut' }}
          />
        ))}
      </svg>
    </motion.div>
  );
}

export function FloatingPrices() {
  /** Fewer, slower, very subtle tickers (ambient only). */
  const prices = [
    { symbol: 'EUR/USD', value: '1.0847', change: '+0.12%' },
    { symbol: 'GBP/USD', value: '1.2691', change: '-0.08%' },
    { symbol: 'BRENT', value: '78.42', change: '+1.24%' },
    { symbol: 'DAX', value: '17,892', change: '+0.67%' },
  ];

  const leftPct = ['12%', '32%', '52%', '68%'];

  return (
    <div className="absolute inset-0 overflow-hidden pointer-events-none">
      {prices.map((price, i) => (
        <motion.div
          key={i}
          className="absolute max-w-[min(100%,12rem)] text-xs font-mono text-white/[0.09]"
          initial={{ y: -40, opacity: 0 }}
          animate={{ y: window.innerHeight + 40, opacity: [0, 0.14, 0.14, 0] }}
          transition={{
            duration: 32 + i * 4,
            repeat: Infinity,
            delay: i * 5,
            ease: 'linear',
          }}
          style={{ left: leftPct[i] }}
        >
          <div className="whitespace-nowrap">
            <span>{price.symbol}</span>
            <span className="ml-1.5">{price.value}</span>
            <span className="ml-1.5 text-white/[0.08]">{price.change}</span>
          </div>
        </motion.div>
      ))}
    </div>
  );
}

export function DiffuseLogo() {
  return (
    <div className="absolute inset-0 flex items-center justify-center pointer-events-none">
      <div className="text-[20rem] font-black text-white/[0.025] select-none tracking-tighter">N</div>
    </div>
  );
}

export function ParticleField() {
  const particles = Array.from({ length: 16 }, (_, i) => ({
    id: i,
    x: Math.random() * 100,
    y: Math.random() * 100,
    size: Math.random() * 2 + 1.5,
    duration: 18 + Math.random() * 12,
  }));

  return (
    <div className="absolute inset-0 overflow-hidden pointer-events-none">
      {particles.map((p) => (
        <motion.div
          key={p.id}
          className="absolute rounded-full bg-white/[0.06]"
          style={{
            left: `${p.x}%`,
            top: `${p.y}%`,
            width: p.size,
            height: p.size,
          }}
          animate={{ opacity: [0.04, 0.1, 0.04] }}
          transition={{ duration: p.duration, repeat: Infinity, ease: 'easeInOut' }}
        />
      ))}
    </div>
  );
}

/** NDA success ambient – abstract, dynamic background shown after confirmation fade-out. */
export function NDASuccessAmbient() {
  const particles = Array.from({ length: 40 }, (_, i) => ({
    id: i,
    x: Math.random() * 100,
    y: Math.random() * 100,
    size: Math.random() * 3 + 1,
    duration: Math.random() * 12 + 6,
    delay: Math.random() * 4,
    xDrift: (Math.random() - 0.5) * 20,
  }));

  const orbs = [
    { x: 15, y: 20, size: 80, duration: 8, color: 'emerald' },
    { x: 85, y: 70, size: 60, duration: 10, color: 'blue' },
    { x: 50, y: 85, size: 100, duration: 12, color: 'emerald' },
  ];

  return (
    <div className="absolute inset-0 overflow-hidden pointer-events-none">
      {particles.map((p) => (
        <motion.div
          key={`p-${p.id}`}
          className="absolute rounded-full bg-white/20"
          style={{
            left: `${p.x}%`,
            top: `${p.y}%`,
            width: p.size,
            height: p.size,
          }}
          animate={{
            y: [0, -40, 0],
            x: [0, p.xDrift, 0],
            opacity: [0.15, 0.35, 0.15],
          }}
          transition={{
            duration: p.duration,
            repeat: Infinity,
            delay: p.delay,
            ease: 'easeInOut',
          }}
        />
      ))}

      {orbs.map((orb, i) => (
        <motion.div
          key={`orb-${i}`}
          className={`absolute rounded-full ${
            orb.color === 'emerald' ? 'bg-emerald-500/10' : orb.color === 'blue' ? 'bg-blue-500/10' : 'bg-amber-500/10'
          }`}
          style={{
            left: `${orb.x}%`,
            top: `${orb.y}%`,
            width: orb.size,
            height: orb.size,
            marginLeft: -orb.size / 2,
            marginTop: -orb.size / 2,
          }}
          animate={{
            scale: [1, 1.2, 1],
            opacity: [0.08, 0.18, 0.08],
            x: [0, 15, 0],
            y: [0, -10, 0],
          }}
          transition={{
            duration: orb.duration,
            repeat: Infinity,
            delay: i * 0.8,
            ease: 'easeInOut',
          }}
        />
      ))}

      <svg className="absolute inset-0 w-full h-full" viewBox="0 0 100 100" preserveAspectRatio="none">
        <defs>
          <linearGradient id="ndaLineGrad1" x1="0%" y1="0%" x2="100%" y2="100%">
            <stop offset="0%" stopColor="var(--color-primary)" stopOpacity="0" />
            <stop offset="50%" stopColor="var(--color-primary)" stopOpacity="0.15" />
            <stop offset="100%" stopColor="var(--color-primary)" stopOpacity="0" />
          </linearGradient>
          <linearGradient id="ndaLineGrad2" x1="100%" y1="0%" x2="0%" y2="100%">
            <stop offset="0%" stopColor="var(--color-eua)" stopOpacity="0" />
            <stop offset="50%" stopColor="var(--color-eua)" stopOpacity="0.12" />
            <stop offset="100%" stopColor="var(--color-eua)" stopOpacity="0" />
          </linearGradient>
        </defs>
        {[0, 1, 2].map((i) => (
          <motion.path
            key={`path-${i}`}
            d={
              i === 0 ? 'M0,50 Q25,20 50,50 T100,50' : i === 1 ? 'M0,80 Q50,30 100,80' : 'M0,20 Q50,70 100,20'
            }
            fill="none"
            stroke={i === 1 ? 'url(#ndaLineGrad2)' : 'url(#ndaLineGrad1)'}
            strokeWidth="0.5"
            strokeDasharray="4 6"
            initial={{ pathLength: 0, opacity: 0 }}
            animate={{
              pathLength: [0, 1, 1, 0],
              opacity: [0, 0.4, 0.4, 0],
            }}
            transition={{
              duration: 6 + i * 2,
              repeat: Infinity,
              delay: i * 1.5,
              ease: 'easeInOut',
            }}
          />
        ))}
      </svg>

      {[0, 1, 2].map((i) => (
        <motion.div
          key={`ring-${i}`}
          className="absolute left-1/2 top-1/2 w-64 h-64 -ml-32 -mt-32 rounded-full border border-emerald-500/20"
          initial={{ scale: 0.3, opacity: 0 }}
          animate={{ scale: [0.3, 1.5, 1.5], opacity: [0.2, 0, 0] }}
          transition={{
            duration: 4,
            repeat: Infinity,
            delay: i * 1.3,
            ease: 'easeOut',
          }}
        />
      ))}

      <div
        className="absolute inset-0 opacity-[0.03] pointer-events-none"
        style={{
          backgroundImage: `linear-gradient(var(--color-text-inverse) 1px, transparent 1px), linear-gradient(90deg, var(--color-text-inverse) 1px, transparent 1px)`,
          backgroundSize: '40px 40px',
        }}
      />

      <div className="absolute inset-0 flex items-center justify-center pointer-events-none">
        <span className="text-[28rem] font-black text-white/[0.02] select-none tracking-tighter">N</span>
      </div>
    </div>
  );
}
