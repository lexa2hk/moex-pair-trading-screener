import { useState, useEffect } from 'react';
import {
  Box,
  Typography,
  Grid,
  Paper,
  FormControl,
  InputLabel,
  Select,
  MenuItem,
  Skeleton,
  Button,
  Chip,
  alpha,
  useTheme,
  CircularProgress,
} from '@mui/material';
import { Refresh as RefreshIcon } from '@mui/icons-material';
import { useQuery, useQueryClient, useMutation } from '@tanstack/react-query';
import { useSearchParams } from 'react-router-dom';
import { api } from '../api/client';
import ZScoreChart from '../components/ZScoreChart';
import SpreadChart from '../components/SpreadChart';
import PriceChart from '../components/PriceChart';

export default function Charts() {
  const theme = useTheme();
  const queryClient = useQueryClient();
  const [searchParams] = useSearchParams();

  const [symbol1, setSymbol1] = useState(searchParams.get('symbol1') || 'SBER');
  const [symbol2, setSymbol2] = useState(searchParams.get('symbol2') || 'SBERP');
  const [days, setDays] = useState(60);

  // Update from URL params
  useEffect(() => {
    const s1 = searchParams.get('symbol1');
    const s2 = searchParams.get('symbol2');
    if (s1) setSymbol1(s1);
    if (s2) setSymbol2(s2);
  }, [searchParams]);

  const { data: pairsData } = useQuery({
    queryKey: ['activePairs'],
    queryFn: () => api.getActivePairs(),
  });

  const { data: spreadData, isLoading: loadingSpread, refetch: refetchSpread, error: spreadError } = useQuery({
    queryKey: ['spreadData', symbol1, symbol2, days],
    queryFn: () => api.getSpreadChartData(symbol1, symbol2, days),
    enabled: !!symbol1 && !!symbol2,
    retry: 1,
  });

  // Debug logging
  console.log('Spread data:', spreadData?.data, 'Error:', spreadError);

  const { data: price1Data, isLoading: loadingPrice1 } = useQuery({
    queryKey: ['ohlcv', symbol1, days],
    queryFn: () => api.getOHLCV(symbol1, 24, days),
    enabled: !!symbol1,
  });

  const { data: price2Data, isLoading: loadingPrice2 } = useQuery({
    queryKey: ['ohlcv', symbol2, days],
    queryFn: () => api.getOHLCV(symbol2, 24, days),
    enabled: !!symbol2,
  });

  const { data: metricsData } = useQuery({
    queryKey: ['pairMetrics', symbol1, symbol2],
    queryFn: () => api.analyzePair(symbol1, symbol2, false),
    enabled: !!symbol1 && !!symbol2,
  });

  // Mutation for force refresh
  const refreshMutation = useMutation({
    mutationFn: () => api.analyzePair(symbol1, symbol2, true), // force_refresh=true
    onSuccess: () => {
      // Invalidate all queries to get fresh data (must match exact query keys)
      queryClient.invalidateQueries({ queryKey: ['spreadData', symbol1, symbol2, days] });
      queryClient.invalidateQueries({ queryKey: ['ohlcv', symbol1, days] });
      queryClient.invalidateQueries({ queryKey: ['ohlcv', symbol2, days] });
      queryClient.invalidateQueries({ queryKey: ['pairMetrics', symbol1, symbol2] });
      queryClient.invalidateQueries({ queryKey: ['activePairs'] });
      // Force refetch
      refetchSpread();
    },
  });

  const pairs = pairsData?.data || [];
  const metrics = metricsData?.data;

  const handleRefresh = () => {
    refreshMutation.mutate();
  };

  // Create unique symbol list from pairs
  const symbols = Array.from(
    new Set(pairs.flatMap((p) => [p.symbol1, p.symbol2]))
  );

  return (
    <Box>
      {/* Header */}
      <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', mb: 3 }}>
        <Box>
          <Typography variant="h5" sx={{ fontWeight: 700, mb: 1 }}>
            Charts
          </Typography>
          <Typography variant="body2" sx={{ color: 'text.secondary' }}>
            Visualize spread and Z-Score for trading pairs
          </Typography>
        </Box>
        <Button
          variant="outlined"
          startIcon={refreshMutation.isPending ? <CircularProgress size={18} /> : <RefreshIcon />}
          onClick={handleRefresh}
          disabled={refreshMutation.isPending}
        >
          {refreshMutation.isPending ? 'Refreshing...' : 'Refresh Data'}
        </Button>
      </Box>

      {/* Controls */}
      <Paper sx={{ p: 2, mb: 3 }}>
        <Grid container spacing={2} alignItems="center">
          <Grid size={{ xs: 12, sm: 4, md: 3 }}>
            <FormControl fullWidth size="small">
              <InputLabel>Symbol 1</InputLabel>
              <Select
                value={symbol1}
                label="Symbol 1"
                onChange={(e) => setSymbol1(e.target.value)}
              >
                {symbols.length > 0 ? (
                  symbols.map((s) => (
                    <MenuItem key={s} value={s}>
                      {s}
                    </MenuItem>
                  ))
                ) : (
                  <>
                    <MenuItem value="SBER">SBER</MenuItem>
                    <MenuItem value="SBERP">SBERP</MenuItem>
                    <MenuItem value="GAZP">GAZP</MenuItem>
                    <MenuItem value="LKOH">LKOH</MenuItem>
                    <MenuItem value="ROSN">ROSN</MenuItem>
                    <MenuItem value="VTBR">VTBR</MenuItem>
                  </>
                )}
              </Select>
            </FormControl>
          </Grid>
          <Grid size={{ xs: 12, sm: 4, md: 3 }}>
            <FormControl fullWidth size="small">
              <InputLabel>Symbol 2</InputLabel>
              <Select
                value={symbol2}
                label="Symbol 2"
                onChange={(e) => setSymbol2(e.target.value)}
              >
                {symbols.length > 0 ? (
                  symbols.filter((s) => s !== symbol1).map((s) => (
                    <MenuItem key={s} value={s}>
                      {s}
                    </MenuItem>
                  ))
                ) : (
                  <>
                    <MenuItem value="SBER">SBER</MenuItem>
                    <MenuItem value="SBERP">SBERP</MenuItem>
                    <MenuItem value="GAZP">GAZP</MenuItem>
                    <MenuItem value="LKOH">LKOH</MenuItem>
                    <MenuItem value="ROSN">ROSN</MenuItem>
                    <MenuItem value="VTBR">VTBR</MenuItem>
                  </>
                )}
              </Select>
            </FormControl>
          </Grid>
          <Grid size={{ xs: 12, sm: 4, md: 2 }}>
            <FormControl fullWidth size="small">
              <InputLabel>Period</InputLabel>
              <Select value={days} label="Period" onChange={(e) => setDays(e.target.value as number)}>
                <MenuItem value={30}>30 Days</MenuItem>
                <MenuItem value={60}>60 Days</MenuItem>
                <MenuItem value={90}>90 Days</MenuItem>
                <MenuItem value={180}>180 Days</MenuItem>
              </Select>
            </FormControl>
          </Grid>
          {metrics && (
            <Grid size={{ xs: 12, md: 4 }}>
              <Box sx={{ display: 'flex', gap: 1, flexWrap: 'wrap' }}>
                <Chip
                  label={metrics.is_cointegrated ? 'Cointegrated' : 'Not Cointegrated'}
                  color={metrics.is_cointegrated ? 'success' : 'error'}
                  size="small"
                />
                <Chip
                  label={`Corr: ${(metrics.correlation * 100).toFixed(0)}%`}
                  size="small"
                  sx={{
                    background: alpha(theme.palette.primary.main, 0.1),
                    color: 'primary.main',
                  }}
                />
                <Chip
                  label={`β: ${metrics.hedge_ratio.toFixed(3)}`}
                  size="small"
                  variant="outlined"
                />
              </Box>
            </Grid>
          )}
        </Grid>
      </Paper>

      {/* Charts Grid */}
      <Grid container spacing={3}>
        {/* Z-Score Chart */}
        <Grid size={12}>
          {loadingSpread ? (
            <Skeleton variant="rectangular" height={350} sx={{ borderRadius: 3 }} />
          ) : spreadData?.data ? (
            <ZScoreChart
              data={spreadData.data}
              symbol1={symbol1}
              symbol2={symbol2}
              height={300}
            />
          ) : (
            <Paper sx={{ height: 350, display: 'flex', alignItems: 'center', justifyContent: 'center', flexDirection: 'column', gap: 1 }}>
              <Typography variant="body2" sx={{ color: 'text.secondary' }}>
                {spreadError ? `Error loading chart: ${(spreadError as Error).message}` : 'No Z-Score data available. Click Refresh Data to analyze.'}
              </Typography>
              <Button size="small" variant="outlined" onClick={handleRefresh} disabled={refreshMutation.isPending}>
                {refreshMutation.isPending ? 'Refreshing...' : 'Refresh Data'}
              </Button>
            </Paper>
          )}
        </Grid>

        {/* Spread Chart */}
        <Grid size={12}>
          {loadingSpread ? (
            <Skeleton variant="rectangular" height={350} sx={{ borderRadius: 3 }} />
          ) : spreadData?.data ? (
            <SpreadChart
              data={spreadData.data}
              symbol1={symbol1}
              symbol2={symbol2}
              height={300}
            />
          ) : (
            <Paper sx={{ height: 350, display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
              <Typography variant="body2" sx={{ color: 'text.secondary' }}>
                No data available
              </Typography>
            </Paper>
          )}
        </Grid>

        {/* Individual Price Charts */}
        <Grid size={{ xs: 12, md: 6 }}>
          {loadingPrice1 ? (
            <Skeleton variant="rectangular" height={300} sx={{ borderRadius: 3 }} />
          ) : price1Data?.data ? (
            <PriceChart data={price1Data.data} symbol={symbol1} height={200} />
          ) : (
            <Paper sx={{ height: 300, display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
              <Typography variant="body2" sx={{ color: 'text.secondary' }}>
                No data for {symbol1}
              </Typography>
            </Paper>
          )}
        </Grid>
        <Grid size={{ xs: 12, md: 6 }}>
          {loadingPrice2 ? (
            <Skeleton variant="rectangular" height={300} sx={{ borderRadius: 3 }} />
          ) : price2Data?.data ? (
            <PriceChart data={price2Data.data} symbol={symbol2} height={200} />
          ) : (
            <Paper sx={{ height: 300, display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
              <Typography variant="body2" sx={{ color: 'text.secondary' }}>
                No data for {symbol2}
              </Typography>
            </Paper>
          )}
        </Grid>
      </Grid>
    </Box>
  );
}

