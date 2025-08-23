"use client";

import { useState, useEffect } from "react";
import { useTheme } from "@mui/material/styles";
import { Breakpoint } from "@mui/material";

export function useResponsive(query: 'up' | 'down' | 'between', start: Breakpoint, end?: Breakpoint) {
  const theme = useTheme();
  const [matches, setMatches] = useState(false);

  useEffect(() => {
    let mediaQuery: MediaQueryList;

    switch (query) {
      case 'up':
        mediaQuery = window.matchMedia(theme.breakpoints.up(start));
        break;
      case 'down':
        mediaQuery = window.matchMedia(theme.breakpoints.down(start));
        break;
      case 'between':
        if (!end) throw new Error('End breakpoint is required for "between" query');
        mediaQuery = window.matchMedia(theme.breakpoints.between(start, end));
        break;
      default:
        throw new Error(`Invalid query: ${query}`);
    }

    setMatches(mediaQuery.matches);

    const handleChange = (event: MediaQueryListEvent) => {
      setMatches(event.matches);
    };

    mediaQuery.addEventListener('change', handleChange);

    return () => {
      mediaQuery.removeEventListener('change', handleChange);
    };
  }, [query, start, end, theme]);

  return matches;
}

// Convenience hooks
export const useIsMobile = () => useResponsive('down', 'md');
export const useIsTablet = () => useResponsive('between', 'md', 'lg');
export const useIsDesktop = () => useResponsive('up', 'lg');

// Hook to get current breakpoint
export function useCurrentBreakpoint() {
  const theme = useTheme();
  const [breakpoint, setBreakpoint] = useState<Breakpoint>('xs');

  useEffect(() => {
    const breakpoints: Breakpoint[] = ['xs', 'sm', 'md', 'lg', 'xl'];
    
    const updateBreakpoint = () => {
      for (let i = breakpoints.length - 1; i >= 0; i--) {
        const bp = breakpoints[i];
        if (window.matchMedia(theme.breakpoints.up(bp)).matches) {
          setBreakpoint(bp);
          break;
        }
      }
    };

    updateBreakpoint();

    const mediaQueries = breakpoints.map(bp => {
      const mq = window.matchMedia(theme.breakpoints.up(bp));
      mq.addEventListener('change', updateBreakpoint);
      return mq;
    });

    return () => {
      mediaQueries.forEach(mq => {
        mq.removeEventListener('change', updateBreakpoint);
      });
    };
  }, [theme]);

  return breakpoint;
}