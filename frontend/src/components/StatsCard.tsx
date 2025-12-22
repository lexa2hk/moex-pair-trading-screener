import { Box, Paper, Typography, alpha, useTheme } from '@mui/material';
import { ReactNode } from 'react';

interface StatsCardProps {
  title: string;
  value: string | number;
  subtitle?: string;
  icon: ReactNode;
  color?: 'primary' | 'success' | 'error' | 'warning' | 'secondary';
  trend?: {
    value: number;
    isPositive: boolean;
  };
}

export default function StatsCard({ title, value, subtitle, icon, color = 'primary', trend }: StatsCardProps) {
  const theme = useTheme();
  const colorValue = theme.palette[color].main;

  return (
    <Paper
      sx={{
        p: 3,
        position: 'relative',
        overflow: 'hidden',
        height: '100%',
        '&::before': {
          content: '""',
          position: 'absolute',
          top: 0,
          left: 0,
          right: 0,
          height: 3,
          background: `linear-gradient(90deg, ${colorValue} 0%, ${alpha(colorValue, 0.3)} 100%)`,
        },
      }}
    >
      <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start' }}>
        <Box>
          <Typography
            variant="overline"
            sx={{ color: 'text.secondary', display: 'block', mb: 0.5 }}
          >
            {title}
          </Typography>
          <Typography
            variant="h4"
            sx={{
              fontWeight: 700,
              color: colorValue,
              display: 'flex',
              alignItems: 'baseline',
              gap: 1,
            }}
          >
            {value}
            {trend && (
              <Typography
                component="span"
                variant="body2"
                sx={{
                  color: trend.isPositive ? 'success.main' : 'error.main',
                  fontWeight: 600,
                }}
              >
                {trend.isPositive ? '+' : ''}{trend.value}%
              </Typography>
            )}
          </Typography>
          {subtitle && (
            <Typography variant="body2" sx={{ color: 'text.secondary', mt: 0.5 }}>
              {subtitle}
            </Typography>
          )}
        </Box>
        <Box
          sx={{
            width: 48,
            height: 48,
            borderRadius: 2,
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            background: alpha(colorValue, 0.1),
            color: colorValue,
          }}
        >
          {icon}
        </Box>
      </Box>
    </Paper>
  );
}

