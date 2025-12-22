import { Box, Typography, Grid, Paper, Button, Skeleton, alpha, useTheme } from '@mui/material';
import { Add as AddIcon } from '@mui/icons-material';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { api } from '../api/client';
import PositionsTable from '../components/PositionsTable';

export default function Positions() {
  const theme = useTheme();
  const queryClient = useQueryClient();

  const { data: positionsData, isLoading } = useQuery({
    queryKey: ['positions'],
    queryFn: () => api.getPositions(),
    refetchInterval: 30000,
  });

  const closePositionMutation = useMutation({
    mutationFn: ({ symbol1, symbol2 }: { symbol1: string; symbol2: string }) =>
      api.closePosition(symbol1, symbol2),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['positions'] });
      queryClient.invalidateQueries({ queryKey: ['dashboardStats'] });
    },
  });

  const positions = positionsData?.data || [];

  // Calculate stats
  const longPositions = positions.filter((p) => p.position_type === 'LONG_SPREAD').length;
  const shortPositions = positions.filter((p) => p.position_type === 'SHORT_SPREAD').length;
  const totalPnl = positions.reduce((sum, p) => sum + (p.pnl_percent || 0), 0);
  const avgPnl = positions.length > 0 ? totalPnl / positions.length : 0;

  const handleClosePosition = (symbol1: string, symbol2: string) => {
    if (confirm(`Close position for ${symbol1}/${symbol2}?`)) {
      closePositionMutation.mutate({ symbol1, symbol2 });
    }
  };

  return (
    <Box>
      {/* Header */}
      <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', mb: 3 }}>
        <Box>
          <Typography variant="h5" sx={{ fontWeight: 700, mb: 1 }}>
            Open Positions
          </Typography>
          <Typography variant="body2" sx={{ color: 'text.secondary' }}>
            Track and manage your active trading positions
          </Typography>
        </Box>
      </Box>

      {/* Stats Cards */}
      <Grid container spacing={3} sx={{ mb: 3 }}>
        <Grid size={{ xs: 6, sm: 3 }}>
          <Paper sx={{ p: 2, textAlign: 'center' }}>
            <Typography variant="h4" sx={{ fontWeight: 700, color: 'primary.main' }}>
              {positions.length}
            </Typography>
            <Typography variant="caption" sx={{ color: 'text.secondary' }}>
              Total Positions
            </Typography>
          </Paper>
        </Grid>
        <Grid size={{ xs: 6, sm: 3 }}>
          <Paper sx={{ p: 2, textAlign: 'center' }}>
            <Typography variant="h4" sx={{ fontWeight: 700, color: 'success.main' }}>
              {longPositions}
            </Typography>
            <Typography variant="caption" sx={{ color: 'text.secondary' }}>
              Long Positions
            </Typography>
          </Paper>
        </Grid>
        <Grid size={{ xs: 6, sm: 3 }}>
          <Paper sx={{ p: 2, textAlign: 'center' }}>
            <Typography variant="h4" sx={{ fontWeight: 700, color: 'error.main' }}>
              {shortPositions}
            </Typography>
            <Typography variant="caption" sx={{ color: 'text.secondary' }}>
              Short Positions
            </Typography>
          </Paper>
        </Grid>
        <Grid size={{ xs: 6, sm: 3 }}>
          <Paper sx={{ p: 2, textAlign: 'center' }}>
            <Typography
              variant="h4"
              sx={{
                fontWeight: 700,
                color: avgPnl >= 0 ? 'success.main' : 'error.main',
              }}
            >
              {avgPnl >= 0 ? '+' : ''}{avgPnl.toFixed(2)}%
            </Typography>
            <Typography variant="caption" sx={{ color: 'text.secondary' }}>
              Average P&L
            </Typography>
          </Paper>
        </Grid>
      </Grid>

      {/* Position Management Info */}
      <Paper sx={{ p: 2, mb: 3, background: alpha(theme.palette.primary.main, 0.05) }}>
        <Typography variant="subtitle2" sx={{ mb: 1 }}>
          Position Management
        </Typography>
        <Typography variant="body2" sx={{ color: 'text.secondary' }}>
          Positions are tracked for monitoring purposes. The system generates exit signals when
          Z-Score crosses the exit threshold or stop-loss level. Actual order execution should be
          done through your broker.
        </Typography>
      </Paper>

      {/* Positions Table */}
      {isLoading ? (
        <Skeleton variant="rectangular" height={400} sx={{ borderRadius: 3 }} />
      ) : (
        <PositionsTable positions={positions} onClose={handleClosePosition} />
      )}

      {/* Risk Guidelines */}
      <Paper sx={{ mt: 3, p: 2 }}>
        <Typography variant="subtitle2" sx={{ mb: 2 }}>
          Risk Management Guidelines
        </Typography>
        <Grid container spacing={3}>
          <Grid size={{ xs: 12, sm: 6, md: 3 }}>
            <Box
              sx={{
                p: 2,
                borderRadius: 2,
                background: alpha(theme.palette.error.main, 0.1),
                border: `1px solid ${alpha(theme.palette.error.main, 0.2)}`,
              }}
            >
              <Typography variant="subtitle2" sx={{ color: 'error.main', mb: 1 }}>
                Stop Loss
              </Typography>
              <Typography variant="caption" sx={{ color: 'text.secondary' }}>
                Close position when Z-Score exceeds ±3.0 standard deviations to limit losses.
              </Typography>
            </Box>
          </Grid>
          <Grid size={{ xs: 12, sm: 6, md: 3 }}>
            <Box
              sx={{
                p: 2,
                borderRadius: 2,
                background: alpha(theme.palette.success.main, 0.1),
                border: `1px solid ${alpha(theme.palette.success.main, 0.2)}`,
              }}
            >
              <Typography variant="subtitle2" sx={{ color: 'success.main', mb: 1 }}>
                Take Profit
              </Typography>
              <Typography variant="caption" sx={{ color: 'text.secondary' }}>
                Close position when Z-Score crosses 0 (mean reversion complete).
              </Typography>
            </Box>
          </Grid>
          <Grid size={{ xs: 12, sm: 6, md: 3 }}>
            <Box
              sx={{
                p: 2,
                borderRadius: 2,
                background: alpha(theme.palette.warning.main, 0.1),
                border: `1px solid ${alpha(theme.palette.warning.main, 0.2)}`,
              }}
            >
              <Typography variant="subtitle2" sx={{ color: 'warning.main', mb: 1 }}>
                Position Sizing
              </Typography>
              <Typography variant="caption" sx={{ color: 'text.secondary' }}>
                Never risk more than 2% of capital per trade. Use proper hedge ratios.
              </Typography>
            </Box>
          </Grid>
          <Grid size={{ xs: 12, sm: 6, md: 3 }}>
            <Box
              sx={{
                p: 2,
                borderRadius: 2,
                background: alpha(theme.palette.primary.main, 0.1),
                border: `1px solid ${alpha(theme.palette.primary.main, 0.2)}`,
              }}
            >
              <Typography variant="subtitle2" sx={{ color: 'primary.main', mb: 1 }}>
                Diversification
              </Typography>
              <Typography variant="caption" sx={{ color: 'text.secondary' }}>
                Maintain multiple uncorrelated pair positions to reduce systematic risk.
              </Typography>
            </Box>
          </Grid>
        </Grid>
      </Paper>
    </Box>
  );
}

