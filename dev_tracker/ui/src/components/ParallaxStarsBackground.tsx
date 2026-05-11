import { useMemo } from "react";

interface Props {
  enabled: boolean;
  reducedMotion: boolean;
}

interface Star {
  top: string;
  left: string;
  size: number;
  opacity: number;
  duration: number;
  delay: number;
}

function seededRandom(seed: number) {
  let value = seed;
  return () => {
    value = (value * 1664525 + 1013904223) % 4294967296;
    return value / 4294967296;
  };
}

export function ParallaxStarsBackground({ enabled, reducedMotion }: Props) {
  const stars = useMemo(() => {
    const next = seededRandom(20260223);
    const count = reducedMotion ? 80 : 140;
    const generated: Star[] = [];

    for (let index = 0; index < count; index += 1) {
      generated.push({
        top: `${Math.round(next() * 100)}%`,
        left: `${Math.round(next() * 100)}%`,
        size: 1 + Math.round(next() * 2),
        opacity: 0.25 + next() * 0.5,
        duration: 8 + next() * 18,
        delay: next() * 8,
      });
    }

    return generated;
  }, [reducedMotion]);

  if (!enabled) {
    return null;
  }

  return (
    <div className="stars-layer" aria-hidden="true">
      {stars.map((star, index) => (
        <span
          key={`star-${index}`}
          style={{
            position: "absolute",
            top: star.top,
            left: star.left,
            width: `${star.size}px`,
            height: `${star.size}px`,
            borderRadius: "999px",
            background: "rgba(184, 224, 255, 0.8)",
            opacity: star.opacity,
            animation: reducedMotion ? "none" : `pulse ${star.duration}s ease-in-out ${star.delay}s infinite`,
          }}
        />
      ))}
      <style>{`@keyframes pulse { 0%, 100% { transform: scale(1); opacity: 0.2; } 50% { transform: scale(1.6); opacity: 0.85; } }`}</style>
    </div>
  );
}
