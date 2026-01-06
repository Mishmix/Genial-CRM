interface AvatarProps {
  name: string;
  size?: 'sm' | 'md' | 'lg' | 'xl';
  className?: string;
}

// Приятные нейтральные цвета для аватаров
const AVATAR_COLORS = [
  'from-violet-500 to-purple-600',
  'from-blue-500 to-indigo-600',
  'from-emerald-500 to-teal-600',
  'from-amber-500 to-orange-600',
  'from-rose-500 to-pink-600',
  'from-cyan-500 to-blue-600',
  'from-fuchsia-500 to-purple-600',
  'from-lime-500 to-green-600',
  'from-sky-500 to-indigo-600',
  'from-teal-500 to-cyan-600',
];

// Генерируем стабильный цвет на основе имени
function getColorFromName(name: string): string {
  let hash = 0;
  for (let i = 0; i < name.length; i++) {
    hash = name.charCodeAt(i) + ((hash << 5) - hash);
  }
  const index = Math.abs(hash) % AVATAR_COLORS.length;
  return AVATAR_COLORS[index];
}

function getInitial(name: string): string {
  return (name || '?').charAt(0).toUpperCase();
}

const sizeClasses = {
  sm: 'w-8 h-8 text-sm',
  md: 'w-10 h-10 text-base',
  lg: 'w-12 h-12 text-lg',
  xl: 'w-16 h-16 text-2xl',
};

export default function Avatar({ name, size = 'md', className = '' }: AvatarProps) {
  const colorClass = getColorFromName(name);
  const initial = getInitial(name);
  const sizeClass = sizeClasses[size];

  return (
    <div 
      className={`${sizeClass} rounded-2xl bg-gradient-to-br ${colorClass} flex items-center justify-center text-white font-semibold shadow-lg ${className}`}
    >
      {initial}
    </div>
  );
}
