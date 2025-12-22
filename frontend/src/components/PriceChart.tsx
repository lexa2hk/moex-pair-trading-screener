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
} from 'chart.js';
import { Line } from 'react-chartjs-2';
import type { OHLCVDataPoint } from '../api/client';

ChartJS.register(
  CategoryScale,
  LinearScale,
  PointElement,
  LineElement,
  Title,
  Tooltip,
  Legend
);

interface PriceChartProps {
  data: OHLCVDataPoint[];
  symbol: string;
  height?: number;
}

// Detect if data is intraday (minute/hourly) or daily
function isIntradayData(data: OHLCVDataPoint[]): boolean {
  if (data.length < 2) return false;
  
  const first = new Date(data[0].timestamp);
  const second = new Date(data[1].timestamp);
  const diffMs = Math.abs(second.getTime() - first.getTime());
  const diffHours = diffMs / (1000 * 60 * 60);
  
  // If difference between points is less than 24 hours, it's intraday
  return diffHours < 24;
}

// Format timestamp based on data type
function formatTimestamp(ts: string, isIntraday: boolean): string {
  const date = new Date(ts);
  
  if (isIntraday) {
    return date.toLocaleTimeString('ru-RU', { 
      hour: '2-digit', 
      minute: '2-digit',
      day: '2-digit',
      month: 'short'
    });
  } else {
    return date.toLocaleDateString('ru-RU', { month: 'short', day: 'numeric' });
  }
}

// Format for tooltip
function formatTooltipTimestamp(ts: string): string {
  const date = new Date(ts);
  return date.toLocaleString('ru-RU', {
    day: '2-digit',
    month: 'short',
    hour: '2-digit',
    minute: '2-digit'
  });
}

export default function PriceChart({ data, symbol, height = 250 }: PriceChartProps) {
  const theme = useTheme();

  const chartData = useMemo(() => {
    const isIntraday = isIntradayData(data);
    const labels = data.map((d) => formatTimestamp(d.timestamp, isIntraday));
    const closes = data.map((d) => d.close);

    return {
      labels,
      datasets: [
        {
          label: symbol,
          data: closes,
          borderColor: theme.palette.primary.main,
          backgroundColor: 'transparent',
          tension: 0.3,
          pointRadius: 0,
          pointHoverRadius: 4,
          borderWidth: 2,
        },
      ],
    };
  }, [data, symbol, theme]);

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
          display: false,
        },
        tooltip: {
          backgroundColor: alpha(theme.palette.background.paper, 0.95),
          titleColor: theme.palette.text.primary,
          bodyColor: theme.palette.text.secondary,
          borderColor: alpha(theme.palette.primary.main, 0.2),
          borderWidth: 1,
          padding: 12,
          callbacks: {
            title: (context: { dataIndex: number }[]) => {
              const idx = context[0]?.dataIndex;
              if (idx !== undefined && data[idx]) {
                return formatTooltipTimestamp(data[idx].timestamp);
              }
              return '';
            },
            label: (context: { parsed: { y: number } }) => {
              return `Price: ${context.parsed.y?.toFixed(2)} ₽`;
            },
          },
        },
      },
      scales: {
        x: {
          grid: {
            color: alpha(theme.palette.divider, 0.3),
            drawBorder: false,
          },
          ticks: {
            color: theme.palette.text.secondary,
            font: {
              size: 9,
            },
            maxTicksLimit: 8,
            maxRotation: 45,
            minRotation: 0,
          },
        },
        y: {
          grid: {
            color: alpha(theme.palette.divider, 0.3),
            drawBorder: false,
          },
          ticks: {
            color: theme.palette.text.secondary,
            font: {
              size: 10,
            },
            callback: (value: string | number) => `${value} ₽`,
          },
        },
      },
    }),
    [theme, data]
  );

  const lastPrice = data.length > 0 ? data[data.length - 1].close : null;
  const firstPrice = data.length > 0 ? data[0].close : null;
  const change = lastPrice && firstPrice ? ((lastPrice - firstPrice) / firstPrice) * 100 : null;
  const isIntraday = isIntradayData(data);

  return (
    <Paper sx={{ p: 3 }}>
      <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 2 }}>
        <Box>
          <Typography variant="h6" sx={{ fontWeight: 600 }}>
            {symbol}
          </Typography>
          <Typography variant="body2" sx={{ color: 'text.secondary' }}>
            Price history {isIntraday ? '(Intraday)' : '(Daily)'}
          </Typography>
        </Box>
        <Box sx={{ textAlign: 'right' }}>
          <Typography variant="h5" sx={{ fontWeight: 700 }}>
            {lastPrice?.toFixed(2) || 'N/A'} ₽
          </Typography>
          {change !== null && (
            <Typography
              variant="body2"
              sx={{
                color: change >= 0 ? 'success.main' : 'error.main',
                fontWeight: 600,
              }}
            >
              {change >= 0 ? '+' : ''}{change.toFixed(2)}%
            </Typography>
          )}
        </Box>
      </Box>
      <Box sx={{ height }}>
        <Line data={chartData} options={options} />
      </Box>
    </Paper>
  );
}
