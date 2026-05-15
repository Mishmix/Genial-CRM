import { useEffect, useState } from 'react';

export default function BackgroundEffects() {
  const [particles, setParticles] = useState<Array<{
    id: number;
    x: number;
    y: number;
    size: number;
    speedX: number;
    speedY: number;
    opacity: number;
    color: string;
  }>>([]);

  useEffect(() => {
    // Generate particles
    const colors = ['#8b5cf6', '#a78bfa', '#38bdf8', '#ec4899'];
    const newParticles = Array.from({ length: 35 }, (_, i) => ({
      id: i,
      x: Math.random() * 100,
      y: Math.random() * 100,
      size: 2 + Math.random() * 3,
      speedX: (Math.random() - 0.5) * 0.3,
      speedY: (Math.random() - 0.5) * 0.3,
      opacity: 0.3 + Math.random() * 0.4,
      color: colors[i % colors.length],
    }));
    setParticles(newParticles);

    // Animate particles
    const interval = setInterval(() => {
      setParticles(prev => prev.map(p => {
        let newX = p.x + p.speedX;
        let newY = p.y + p.speedY;
        
        // Bounce off edges
        if (newX < 0 || newX > 100) p.speedX *= -1;
        if (newY < 0 || newY > 100) p.speedY *= -1;
        
        newX = Math.max(0, Math.min(100, newX));
        newY = Math.max(0, Math.min(100, newY));
        
        return { ...p, x: newX, y: newY };
      }));
    }, 50);

    return () => clearInterval(interval);
  }, []);

  // Floating orbs
  const orbs = [
    { size: 600, top: '-200px', left: '-200px', color: 'rgba(139, 92, 246, 0.35)', delay: 0 },
    { size: 500, bottom: '-150px', right: '-150px', color: 'rgba(167, 139, 250, 0.3)', delay: -5 },
    { size: 400, top: '30%', right: '10%', color: 'rgba(56, 189, 248, 0.25)', delay: -10 },
    { size: 350, bottom: '20%', left: '15%', color: 'rgba(236, 72, 153, 0.2)', delay: -15 },
  ];

  return (
    <>
      {/* Animated glow orbs */}
      {orbs.map((orb, i) => (
        <div
          key={i}
          className="glow-orb"
          style={{
            width: `${orb.size}px`,
            height: `${orb.size}px`,
            top: orb.top,
            bottom: orb.bottom,
            left: orb.left,
            right: orb.right,
            background: `radial-gradient(circle, ${orb.color} 0%, transparent 70%)`,
            animationDelay: `${orb.delay}s`,
          }}
        />
      ))}

      {/* Floating particles - NO cursor interaction */}
      <div className="fixed inset-0 pointer-events-none z-0 overflow-hidden">
        {particles.map((p) => (
          <div
            key={p.id}
            className="absolute rounded-full transition-all duration-1000 ease-linear"
            style={{
              left: `${p.x}%`,
              top: `${p.y}%`,
              width: `${p.size}px`,
              height: `${p.size}px`,
              opacity: p.opacity,
              background: p.color,
              boxShadow: `0 0 ${p.size * 3}px ${p.color}`,
            }}
          />
        ))}
      </div>

      {/* Grid overlay with gradient mask */}
      <div 
        className="fixed inset-0 pointer-events-none z-0 bg-grid"
        style={{
          opacity: 0.5,
          maskImage: 'radial-gradient(ellipse 90% 70% at 50% 50%, black 30%, transparent 100%)',
          WebkitMaskImage: 'radial-gradient(ellipse 90% 70% at 50% 50%, black 30%, transparent 100%)',
        }}
      />

      {/* Top gradient line */}
      <div 
        className="fixed top-0 left-0 right-0 h-px pointer-events-none z-50"
        style={{
          background: 'linear-gradient(90deg, transparent 0%, rgba(139, 92, 246, 0.6) 20%, rgba(167, 139, 250, 0.6) 50%, rgba(56, 189, 248, 0.6) 80%, transparent 100%)',
        }}
      />
    </>
  );
}
