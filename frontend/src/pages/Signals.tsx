import { Box, Typography, Grid, Paper, Chip, Skeleton, alpha, useTheme } from '@mui/material';
import {
  TrendingUp as LongIcon,
  TrendingDown as ShortIcon,
  ExitToApp as ExitIcon,
} from '@mui/icons-material';
import { useQuery } from '@tanstack/react-query';
import { api } from '../api/client';
import SignalsList from '../components/SignalsList';

export default function Signals() {
  const theme = useTheme();

  const { data: signalsData, isLoading } = useQuery({
    queryKey: ['signals'],
    queryFn: () => api.getSignals(100),
    refetchInterval: 30000,
  });

  const signals = signalsData?.data || [];

  // Calculate signal stats
  const longSignals = signals.filter((s) => s.signal_type === 'LONG_SPREAD').length;
  const shortSignals = signals.filter((s) => s.signal_type === 'SHORT_SPREAD').length;
  const exitSignals = signals.filter((s) =>
    ['EXIT_LONG', 'EXIT_SHORT', 'STOP_LOSS'].includes(s.signal_type)
  ).length;

  const strongSignals = signals.filter((s) => s.strength === 'STRONG').length;
  const avgConfidence = signals.length > 0
    ? signals.reduce((sum, s) => sum + s.confidence, 0) / signals.length
    : 0;

  return (
    <Box>
      {/* Header */}
      <Box sx={{ mb: 3 }}>
        <Typography variant="h5" sx={{ fontWeight: 700, mb: 1 }}>
          Trading Signals
        </Typography>
        <Typography variant="body2" sx={{ color: 'text.secondary' }}>
          Real-time trading signals based on statistical analysis
        </Typography>
      </Box>

      {/* Stats Cards */}
      <Grid container spacing={3} sx={{ mb: 3 }}>
        <Grid size={{ xs: 6, sm: 4, md: 2 }}>
          <Paper sx={{ p: 2, textAlign: 'center' }}>
            <Typography variant="h4" sx={{ fontWeight: 700, color: 'primary.main' }}>
              {signals.length}
            </Typography>
            <Typography variant="caption" sx={{ color: 'text.secondary' }}>
              Total Signals
            </Typography>
          </Paper>
        </Grid>
        <Grid size={{ xs: 6, sm: 4, md: 2 }}>
          <Paper sx={{ p: 2, textAlign: 'center' }}>
            <Box sx={{ display: 'flex', alignItems: 'center', justifyContent: 'center', gap: 0.5 }}>
              <LongIcon sx={{ color: 'success.main', fontSize: 20 }} />
              <Typography variant="h4" sx={{ fontWeight: 700, color: 'success.main' }}>
                {longSignals}
              </Typography>
            </Box>
            <Typography variant="caption" sx={{ color: 'text.secondary' }}>
              Long Signals
            </Typography>
          </Paper>
        </Grid>
        <Grid size={{ xs: 6, sm: 4, md: 2 }}>
          <Paper sx={{ p: 2, textAlign: 'center' }}>
            <Box sx={{ display: 'flex', alignItems: 'center', justifyContent: 'center', gap: 0.5 }}>
              <ShortIcon sx={{ color: 'error.main', fontSize: 20 }} />
              <Typography variant="h4" sx={{ fontWeight: 700, color: 'error.main' }}>
                {shortSignals}
              </Typography>
            </Box>
            <Typography variant="caption" sx={{ color: 'text.secondary' }}>
              Short Signals
            </Typography>
          </Paper>
        </Grid>
        <Grid size={{ xs: 6, sm: 4, md: 2 }}>
          <Paper sx={{ p: 2, textAlign: 'center' }}>
            <Box sx={{ display: 'flex', alignItems: 'center', justifyContent: 'center', gap: 0.5 }}>
              <ExitIcon sx={{ color: 'warning.main', fontSize: 20 }} />
              <Typography variant="h4" sx={{ fontWeight: 700, color: 'warning.main' }}>
                {exitSignals}
              </Typography>
            </Box>
            <Typography variant="caption" sx={{ color: 'text.secondary' }}>
              Exit Signals
            </Typography>
          </Paper>
        </Grid>
        <Grid size={{ xs: 6, sm: 4, md: 2 }}>
          <Paper sx={{ p: 2, textAlign: 'center' }}>
            <Typography variant="h4" sx={{ fontWeight: 700, color: 'secondary.main' }}>
              {strongSignals}
            </Typography>
            <Typography variant="caption" sx={{ color: 'text.secondary' }}>
              Strong Signals
            </Typography>
          </Paper>
        </Grid>
        <Grid size={{ xs: 6, sm: 4, md: 2 }}>
          <Paper sx={{ p: 2, textAlign: 'center' }}>
            <Typography variant="h4" sx={{ fontWeight: 700 }}>
              {(avgConfidence * 100).toFixed(0)}%
            </Typography>
            <Typography variant="caption" sx={{ color: 'text.secondary' }}>
              Avg Confidence
            </Typography>
          </Paper>
        </Grid>
      </Grid>

      {/* Signal Type Explanation */}
      <Paper sx={{ p: 2, mb: 3 }}>
        <Typography variant="subtitle2" sx={{ mb: 2 }}>
          Signal Types
        </Typography>
        <Grid container spacing={2}>
          <Grid size={{ xs: 12, sm: 6, md: 3 }}>
            <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
              <Chip label="LONG SPREAD" color="success" size="small" />
            </Box>
            <Typography variant="caption" sx={{ color: 'text.secondary', display: 'block', mt: 1 }}>
              Z-Score below entry threshold. Buy Symbol1, Sell Symbol2. Expect spread to increase.
            </Typography>
          </Grid>
          <Grid size={{ xs: 12, sm: 6, md: 3 }}>
            <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
              <Chip label="SHORT SPREAD" color="error" size="small" />
            </Box>
            <Typography variant="caption" sx={{ color: 'text.secondary', display: 'block', mt: 1 }}>
              Z-Score above entry threshold. Sell Symbol1, Buy Symbol2. Expect spread to decrease.
            </Typography>
          </Grid>
          <Grid size={{ xs: 12, sm: 6, md: 3 }}>
            <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
              <Chip label="EXIT" color="warning" size="small" />
            </Box>
            <Typography variant="caption" sx={{ color: 'text.secondary', display: 'block', mt: 1 }}>
              Z-Score crossed exit threshold. Close position and take profit.
            </Typography>
          </Grid>
          <Grid size={{ xs: 12, sm: 6, md: 3 }}>
            <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
              <Chip label="STOP LOSS" color="error" variant="outlined" size="small" />
            </Box>
            <Typography variant="caption" sx={{ color: 'text.secondary', display: 'block', mt: 1 }}>
              Z-Score exceeded stop loss threshold. Close position to limit losses.
            </Typography>
          </Grid>
        </Grid>
      </Paper>

      {/* Signals List */}
      {isLoading ? (
        <Skeleton variant="rectangular" height={500} sx={{ borderRadius: 3 }} />
      ) : (
        <SignalsList signals={signals} maxHeight={600} />
      )}
    </Box>
  );
}

