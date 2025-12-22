import { Grid, Box, Typography, Skeleton } from '@mui/material';
import {
  TrendingUp as PairsIcon,
  NotificationsActive as SignalsIcon,
  AccountBalance as PositionsIcon,
  Link as CointegrationIcon,
} from '@mui/icons-material';
import { useQuery } from '@tanstack/react-query';
import { api } from '../api/client';
import StatsCard from '../components/StatsCard';
import PairsTable from '../components/PairsTable';
import SignalsList from '../components/SignalsList';
import ZScoreChart from '../components/ZScoreChart';
import { useNavigate } from 'react-router-dom';

export default function Dashboard() {
  const navigate = useNavigate();

  const { data: statsData, isLoading: loadingStats } = useQuery({
    queryKey: ['dashboardStats'],
    queryFn: () => api.getDashboardStats(),
    refetchInterval: 30000,
  });

  const { data: pairsData, isLoading: loadingPairs } = useQuery({
    queryKey: ['activePairs'],
    queryFn: () => api.getActivePairs(),
    refetchInterval: 60000,
  });

  const { data: signalsData, isLoading: loadingSignals } = useQuery({
    queryKey: ['signals'],
    queryFn: () => api.getSignals(10),
    refetchInterval: 30000,
  });

  // Get spread data for the first active pair
  const firstPair = pairsData?.data?.[0];
  const { data: spreadData } = useQuery({
    queryKey: ['spreadData', firstPair?.symbol1, firstPair?.symbol2],
    queryFn: () => api.getSpreadChartData(firstPair!.symbol1, firstPair!.symbol2, 30),
    enabled: !!firstPair,
    refetchInterval: 60000,
  });

  const stats = statsData?.data;
  const pairs = pairsData?.data || [];
  const signals = signalsData?.data || [];

  return (
    <Box>
      {/* Stats Cards */}
      <Grid container spacing={3} sx={{ mb: 3 }}>
        <Grid size={{ xs: 12, sm: 6, md: 3 }}>
          {loadingStats ? (
            <Skeleton variant="rectangular" height={140} sx={{ borderRadius: 3 }} />
          ) : (
            <StatsCard
              title="Active Pairs"
              value={stats?.total_pairs || 0}
              subtitle="Monitored pairs"
              icon={<PairsIcon />}
              color="primary"
            />
          )}
        </Grid>
        <Grid size={{ xs: 12, sm: 6, md: 3 }}>
          {loadingStats ? (
            <Skeleton variant="rectangular" height={140} sx={{ borderRadius: 3 }} />
          ) : (
            <StatsCard
              title="Cointegrated"
              value={stats?.cointegrated_pairs || 0}
              subtitle="Tradeable pairs"
              icon={<CointegrationIcon />}
              color="success"
            />
          )}
        </Grid>
        <Grid size={{ xs: 12, sm: 6, md: 3 }}>
          {loadingStats ? (
            <Skeleton variant="rectangular" height={140} sx={{ borderRadius: 3 }} />
          ) : (
            <StatsCard
              title="Active Signals"
              value={stats?.active_signals || 0}
              subtitle="Entry opportunities"
              icon={<SignalsIcon />}
              color="warning"
            />
          )}
        </Grid>
        <Grid size={{ xs: 12, sm: 6, md: 3 }}>
          {loadingStats ? (
            <Skeleton variant="rectangular" height={140} sx={{ borderRadius: 3 }} />
          ) : (
            <StatsCard
              title="Open Positions"
              value={stats?.open_positions || 0}
              subtitle="Current trades"
              icon={<PositionsIcon />}
              color="secondary"
            />
          )}
        </Grid>
      </Grid>

      {/* Main Content */}
      <Grid container spacing={3}>
        {/* Z-Score Chart */}
        <Grid size={{ xs: 12, lg: 8 }}>
          {firstPair && spreadData?.data ? (
            <ZScoreChart
              data={spreadData.data}
              symbol1={firstPair.symbol1}
              symbol2={firstPair.symbol2}
              height={280}
            />
          ) : (
            <Box
              sx={{
                height: 350,
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                bgcolor: 'background.paper',
                borderRadius: 3,
                border: 1,
                borderColor: 'divider',
              }}
            >
              <Typography variant="body2" sx={{ color: 'text.secondary' }}>
                Analyze a pair to see the Z-Score chart
              </Typography>
            </Box>
          )}
        </Grid>

        {/* Recent Signals */}
        <Grid size={{ xs: 12, lg: 4 }}>
          {loadingSignals ? (
            <Skeleton variant="rectangular" height={350} sx={{ borderRadius: 3 }} />
          ) : (
            <SignalsList signals={signals} maxHeight={280} />
          )}
        </Grid>

        {/* Pairs Table */}
        <Grid size={12}>
          <Box sx={{ mb: 2 }}>
            <Typography variant="h6" sx={{ fontWeight: 600 }}>
              Monitored Pairs
            </Typography>
            <Typography variant="body2" sx={{ color: 'text.secondary' }}>
              Active trading pairs with their metrics
            </Typography>
          </Box>
          <PairsTable
            pairs={pairs}
            isLoading={loadingPairs}
            onViewChart={(s1, s2) => navigate(`/charts?symbol1=${s1}&symbol2=${s2}`)}
            onAnalyze={(s1, s2) => navigate(`/pairs?analyze=${s1}-${s2}`)}
          />
        </Grid>
      </Grid>
    </Box>
  );
}

