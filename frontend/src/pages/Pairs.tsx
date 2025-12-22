import { Box, Typography, Grid, Paper, Chip, alpha, useTheme } from '@mui/material';
import { useQuery, useQueryClient, useMutation } from '@tanstack/react-query';
import { useNavigate } from 'react-router-dom';
import { api, type PairMetrics } from '../api/client';
import PairsTable from '../components/PairsTable';
import PairAnalyzer from '../components/PairAnalyzer';

export default function Pairs() {
  const theme = useTheme();
  const navigate = useNavigate();
  const queryClient = useQueryClient();

  const { data: pairsData, isLoading } = useQuery({
    queryKey: ['activePairs'],
    queryFn: () => api.getActivePairs(),
    refetchInterval: 60000,
  });

  const pairs = pairsData?.data || [];

  const removeMutation = useMutation({
    mutationFn: ({ s1, s2 }: { s1: string; s2: string }) => api.removePair(s1, s2),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['activePairs'] });
      queryClient.invalidateQueries({ queryKey: ['dashboardStats'] });
    },
  });

  const handlePairAnalyzed = (metrics: PairMetrics) => {
    queryClient.invalidateQueries({ queryKey: ['activePairs'] });
  };

  const handleRemovePair = (s1: string, s2: string) => {
    if (confirm(`Remove pair ${s1}/${s2}?`)) {
      removeMutation.mutate({ s1, s2 });
    }
  };

  // Calculate stats (excluding pending pairs)
  const analyzedPairs = pairs.filter((p) => p.correlation !== 0 || p.is_cointegrated);
  const pendingCount = pairs.length - analyzedPairs.length;
  const cointegratedCount = pairs.filter((p) => p.is_cointegrated).length;
  const tradeableCount = pairs.filter((p) => p.is_tradeable).length;
  const avgCorrelation = analyzedPairs.length > 0
    ? analyzedPairs.reduce((sum, p) => sum + Math.abs(p.correlation), 0) / analyzedPairs.length
    : 0;

  return (
    <Box>
      {/* Header with Stats */}
      <Grid container spacing={3} sx={{ mb: 3 }}>
        <Grid size={{ xs: 12, md: 8 }}>
          <Typography variant="h5" sx={{ fontWeight: 700, mb: 1 }}>
            Trading Pairs
          </Typography>
          <Typography variant="body2" sx={{ color: 'text.secondary' }}>
            Analyze and monitor cointegrated pairs for statistical arbitrage opportunities.
          </Typography>
        </Grid>
        <Grid size={{ xs: 12, md: 4 }}>
          <Paper
            sx={{
              p: 2,
              display: 'flex',
              gap: 2,
              justifyContent: 'space-around',
              background: alpha(theme.palette.background.paper, 0.6),
            }}
          >
            <Box sx={{ textAlign: 'center' }}>
              <Typography variant="h5" sx={{ fontWeight: 700, color: 'primary.main' }}>
                {pairs.length}
              </Typography>
              <Typography variant="caption" sx={{ color: 'text.secondary' }}>
                Total Pairs
              </Typography>
            </Box>
            {pendingCount > 0 && (
              <Box sx={{ textAlign: 'center' }}>
                <Typography variant="h5" sx={{ fontWeight: 700, color: 'warning.main' }}>
                  {pendingCount}
                </Typography>
                <Typography variant="caption" sx={{ color: 'text.secondary' }}>
                  Pending
                </Typography>
              </Box>
            )}
            <Box sx={{ textAlign: 'center' }}>
              <Typography variant="h5" sx={{ fontWeight: 700, color: 'success.main' }}>
                {cointegratedCount}
              </Typography>
              <Typography variant="caption" sx={{ color: 'text.secondary' }}>
                Cointegrated
              </Typography>
            </Box>
            <Box sx={{ textAlign: 'center' }}>
              <Typography variant="h5" sx={{ fontWeight: 700, color: 'info.main' }}>
                {tradeableCount}
              </Typography>
              <Typography variant="caption" sx={{ color: 'text.secondary' }}>
                Tradeable
              </Typography>
            </Box>
            <Box sx={{ textAlign: 'center' }}>
              <Typography variant="h5" sx={{ fontWeight: 700 }}>
                {(avgCorrelation * 100).toFixed(0)}%
              </Typography>
              <Typography variant="caption" sx={{ color: 'text.secondary' }}>
                Avg Corr
              </Typography>
            </Box>
          </Paper>
        </Grid>
      </Grid>

      {/* Pair Analyzer */}
      <Box sx={{ mb: 3 }}>
        <PairAnalyzer onPairAnalyzed={handlePairAnalyzed} />
      </Box>

      {/* Pairs Table */}
      <Box sx={{ mb: 2, display: 'flex', alignItems: 'center', gap: 2 }}>
        <Typography variant="h6" sx={{ fontWeight: 600 }}>
          Active Pairs
        </Typography>
        <Chip
          label={`${pairs.length} pairs`}
          size="small"
          sx={{ fontSize: '0.7rem' }}
        />
      </Box>

      <PairsTable
        pairs={pairs}
        isLoading={isLoading}
        onViewChart={(s1, s2) => navigate(`/charts?symbol1=${s1}&symbol2=${s2}`)}
        onAnalyze={(s1, s2) => {
          // Force re-analyze the pair
          api.analyzePair(s1, s2, true).then(() => {
            queryClient.invalidateQueries({ queryKey: ['activePairs'] });
          });
        }}
        onRemove={handleRemovePair}
      />

      {/* Legend */}
      <Paper sx={{ mt: 3, p: 2 }}>
        <Typography variant="subtitle2" sx={{ mb: 1 }}>
          Metrics Legend
        </Typography>
        <Grid container spacing={2}>
          <Grid size={{ xs: 12, sm: 6, md: 3 }}>
            <Typography variant="caption" sx={{ color: 'text.secondary', display: 'block' }}>
              <strong>Correlation:</strong> Statistical measure of how two securities move in relation.
              Higher is better (&gt;80% ideal).
            </Typography>
          </Grid>
          <Grid size={{ xs: 12, sm: 6, md: 3 }}>
            <Typography variant="caption" sx={{ color: 'text.secondary', display: 'block' }}>
              <strong>Cointegration:</strong> Long-term equilibrium relationship. Pairs must be
              cointegrated for mean reversion trading.
            </Typography>
          </Grid>
          <Grid size={{ xs: 12, sm: 6, md: 3 }}>
            <Typography variant="caption" sx={{ color: 'text.secondary', display: 'block' }}>
              <strong>Half-Life:</strong> Time for spread to revert halfway to mean.
              Lower is better (5-20 days ideal).
            </Typography>
          </Grid>
          <Grid size={{ xs: 12, sm: 6, md: 3 }}>
            <Typography variant="caption" sx={{ color: 'text.secondary', display: 'block' }}>
              <strong>Hurst Exponent:</strong> Measure of mean reversion tendency.
              Below 0.5 indicates mean reversion.
            </Typography>
          </Grid>
        </Grid>
      </Paper>
    </Box>
  );
}

