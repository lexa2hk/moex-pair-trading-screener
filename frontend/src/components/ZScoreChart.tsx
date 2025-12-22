import { useMemo } from 'react';
import { Box, Paper, Typography, alpha, useTheme } from '@mui/material';
import {
  Chart as ChartJS,
  CategoryScale,
  LinearScale,
  PointElement,
  LineElement,
  Title,
  Tooltip,
  Legend,
  Filler,
} from 'chart.js';
import { Line } from 'react-chartjs-2';
import type { SpreadChartData } from '../api/client';

ChartJS.register(
  CategoryScale,
  LinearScale,
  PointElement,
  LineElement,
  Title,
  Tooltip,
  Legend,
  Filler
);

interface ZScoreChartProps {
  data: SpreadChartData;
  symbol1: string;
  symbol2: string;
  height?: number;
}

// Detect if data is intraday (minute/hourly) or daily
function isIntradayData(timestamps: string[]): boolean {
  if (timestamps.length < 2) return false;
  
  const first = new Date(timestamps[0]);
  const second = new Date(timestamps[1]);
  const diffMs = Math.abs(second.getTime() - first.getTime());
  const diffHours = diffMs / (1000 * 60 * 60);
  
  // If difference between points is less than 24 hours, it's intraday
  return diffHours < 24;
}

// Format timestamp based on data type
function formatTimestamp(ts: string, isIntraday: boolean): string {
  const date = new Date(ts);
  
  if (isIntraday) {
    // For intraday: show date + time for first point of each day, otherwise just time
    return date.toLocaleTimeString('ru-RU', { 
      hour: '2-digit', 
      minute: '2-digit',
      day: '2-digit',
      month: 'short'
    });
  } else {
    // For daily: show short date
    return date.toLocaleDateString('ru-RU', { month: 'short', day: 'numeric' });
  }
}

// Format for tooltip (always show full datetime)
function formatTooltipTimestamp(ts: string): string {
  const date = new Date(ts);
  return date.toLocaleString('ru-RU', {
    day: '2-digit',
    month: 'short',
    hour: '2-digit',
    minute: '2-digit'
  });
}

export default function ZScoreChart({ data, symbol1, symbol2, height = 300 }: ZScoreChartProps) {
  const theme = useTheme();

  const chartData = useMemo(() => {
    const isIntraday = isIntradayData(data.timestamps);
    
    const labels = data.timestamps.map((ts) => formatTimestamp(ts, isIntraday));

    return {
      labels,
      rawTimestamps: data.timestamps, // Keep raw timestamps for tooltip
      datasets: [
        {
          label: 'Z-Score',
          data: data.zscore,
          borderColor: theme.palette.primary.main,
          backgroundColor: alpha(theme.palette.primary.main, 0.1),
          fill: true,
          tension: 0.4,
          pointRadius: 0,
          pointHoverRadius: 4,
          borderWidth: 2,
        },
        {
          label: 'Upper Threshold',
          data: Array(data.timestamps.length).fill(data.upper_threshold),
          borderColor: theme.palette.error.main,
          borderDash: [5, 5],
          borderWidth: 1.5,
          pointRadius: 0,
          fill: false,
        },
        {
          label: 'Lower Threshold',
          data: Array(data.timestamps.length).fill(data.lower_threshold),
          borderColor: theme.palette.success.main,
          borderDash: [5, 5],
          borderWidth: 1.5,
          pointRadius: 0,
          fill: false,
        },
        {
          label: 'Exit',
          data: Array(data.timestamps.length).fill(data.exit_threshold),
          borderColor: theme.palette.warning.main,
          borderDash: [3, 3],
          borderWidth: 1,
          pointRadius: 0,
          fill: false,
        },
      ],
    };
  }, [data, theme]);

  const options = useMemo(
    () => ({
      responsive: true,
      maintainAspectRatio: false,
      interaction: {
        mode: 'index' as const,
        intersect: false,
      },
      plugins: {
        legend: {
          display: true,
          position: 'top' as const,
          labels: {
            color: theme.palette.text.secondary,
            font: {
              family: theme.typography.fontFamily,
              size: 11,
            },
            usePointStyle: true,
            pointStyle: 'line',
            padding: 16,
          },
        },
        tooltip: {
          backgroundColor: alpha(theme.palette.background.paper, 0.95),
          titleColor: theme.palette.text.primary,
          bodyColor: theme.palette.text.secondary,
          borderColor: alpha(theme.palette.primary.main, 0.2),
          borderWidth: 1,
          padding: 12,
          titleFont: {
            family: theme.typography.fontFamily,
            size: 12,
            weight: 600,
          },
          bodyFont: {
            family: theme.typography.fontFamily,
            size: 11,
          },
          callbacks: {
            title: (context: { dataIndex: number }[]) => {
              const idx = context[0]?.dataIndex;
              if (idx !== undefined && data.timestamps[idx]) {
                return formatTooltipTimestamp(data.timestamps[idx]);
              }
              return '';
            },
            label: (context: { dataset: { label?: string }; parsed: { y: number } }) => {
              const label = context.dataset.label || '';
              const value = context.parsed.y?.toFixed(4) || 'N/A';
              return `${label}: ${value}`;
            },
          },
        },
      },
      scales: {
        x: {
          grid: {
            color: alpha(theme.palette.divider, 0.5),
            drawBorder: false,
          },
          ticks: {
            color: theme.palette.text.secondary,
            font: {
              family: theme.typography.fontFamily,
              size: 9,
            },
            maxTicksLimit: 12,
            maxRotation: 45,
            minRotation: 0,
          },
        },
        y: {
          grid: {
            color: alpha(theme.palette.divider, 0.5),
            drawBorder: false,
          },
          ticks: {
            color: theme.palette.text.secondary,
            font: {
              family: theme.typography.fontFamily,
              size: 10,
            },
          },
        },
      },
    }),
    [theme, data.timestamps]
  );

  const currentZScore = data.zscore[data.zscore.length - 1];
  const zScoreColor =
    currentZScore >= data.upper_threshold
      ? theme.palette.error.main
      : currentZScore <= data.lower_threshold
        ? theme.palette.success.main
        : theme.palette.primary.main;

  const isIntraday = isIntradayData(data.timestamps);

  return (
    <Paper sx={{ p: 3, height: '100%' }}>
      <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 2 }}>
        <Box>
          <Typography variant="h6" sx={{ fontWeight: 600 }}>
            Z-Score: {symbol1}/{symbol2}
          </Typography>
          <Typography variant="body2" sx={{ color: 'text.secondary' }}>
            Mean reversion indicator {isIntraday ? '(Intraday)' : '(Daily)'}
          </Typography>
        </Box>
        <Box sx={{ textAlign: 'right' }}>
          <Typography
            variant="h5"
            sx={{ fontWeight: 700, color: zScoreColor }}
          >
            {currentZScore?.toFixed(4) || 'N/A'}
          </Typography>
          <Typography variant="caption" sx={{ color: 'text.secondary' }}>
            Current Z-Score
          </Typography>
        </Box>
      </Box>
      <Box sx={{ height }}>
        <Line data={chartData} options={options} />
      </Box>
    </Paper>
  );
}
