import { useState, useEffect, ReactNode } from 'react';

interface PageWrapperProps {
  children: ReactNode;
  loading?: boolean;
}

export default function PageWrapper({ children, loading = false }: PageWrapperProps) {
  const [isLoaded, setIsLoaded] = useState(false);

  useEffect(() => {
    if (!loading) {
      // Small delay to ensure DOM is ready
      const timer = setTimeout(() => setIsLoaded(true), 50);
      return () => clearTimeout(timer);
    } else {
      setIsLoaded(false);
    }
  }, [loading]);

  return (
    <div className={`page-content ${isLoaded ? 'loaded' : ''}`}>
      {children}
    </div>
  );
}
