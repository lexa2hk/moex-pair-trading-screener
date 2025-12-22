import { useState } from 'react';
import {
  Paper,
  Box,
  Typography,
  TextField,
  Button,
  Grid,
  Alert,
  CircularProgress,
  Autocomplete,
  alpha,
  useTheme,
  Snackbar,
} from '@mui/material';
import { Search as SearchIcon, Add as AddIcon } from '@mui/icons-material';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { api, type Instrument, type PairMetrics } from '../api/client';
import { AxiosError } from 'axios';

interface PairAnalyzerProps {
  onPairAnalyzed?: (metrics: PairMetrics) => void;
}

export default function PairAnalyzer({ onPairAnalyzed }: PairAnalyzerProps) {
  const theme = useTheme();
  const queryClient = useQueryClient();
  const [symbol1, setSymbol1] = useState<Instrument | null>(null);
  const [symbol2, setSymbol2] = useState<Instrument | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [successMessage, setSuccessMessage] = useState<string | null>(null);

  const { data: instrumentsData, isLoading: loadingInstruments, error: instrumentsError } = useQuery({
    queryKey: ['instruments'],
    queryFn: () => api.getInstruments('shares', 'TQBR', 100),
    staleTime: 5 * 60 * 1000, // 5 minutes
    retry: 2,
  });

  const analyzeMutation = useMutation({
    mutationFn: ({ s1, s2 }: { s1: string; s2: string }) => api.analyzePair(s1, s2),
    onSuccess: (data) => {
      queryClient.invalidateQueries({ queryKey: ['activePairs'] });
      queryClient.invalidateQueries({ queryKey: ['dashboardStats'] });
      onPairAnalyzed?.(data.data);
      setError(null);
      setSuccessMessage(`Pair ${data.data.symbol1}/${data.data.symbol2} analyzed successfully!`);
    },
    onError: (err: AxiosError<{ detail?: string }>) => {
      const message = err.response?.data?.detail || err.message || 'Failed to analyze pair';
      setError(message);
      console.error('Analyze pair error:', err);
    },
  });

  const handleAnalyze = () => {
    if (!symbol1 || !symbol2) {
      setError('Please select both symbols');
      return;
    }
    if (symbol1.secid === symbol2.secid) {
      setError('Please select different symbols');
      return;
    }
    setError(null);
    analyzeMutation.mutate({ s1: symbol1.secid, s2: symbol2.secid });
  };

  const handleQuickAdd = (s1: string, s2: string) => {
    // Directly call the API with the symbol strings
    setError(null);
    analyzeMutation.mutate({ s1, s2 });
  };

  const instruments = instrumentsData?.data || [];

  return (
    <Paper sx={{ p: 3 }}>
      <Typography variant="h6" sx={{ fontWeight: 600, mb: 2 }}>
        Analyze New Pair
      </Typography>
      <Typography variant="body2" sx={{ color: 'text.secondary', mb: 3 }}>
        Select two MOEX instruments to analyze their cointegration and spread metrics.
      </Typography>

      {instrumentsError && (
        <Alert severity="warning" sx={{ mb: 2 }}>
          Failed to load instruments. You can still use the Quick Add buttons below.
        </Alert>
      )}

      <Grid container spacing={2} alignItems="center">
        <Grid size={{ xs: 12, sm: 5 }}>
          <Autocomplete
            options={instruments}
            getOptionLabel={(option) => `${option.secid} - ${option.shortname}`}
            value={symbol1}
            onChange={(_, newValue) => setSymbol1(newValue)}
            loading={loadingInstruments}
            disabled={loadingInstruments}
            renderInput={(params) => (
              <TextField
                {...params}
                label="Symbol 1"
                placeholder={loadingInstruments ? "Loading..." : "Search..."}
                size="small"
                fullWidth
              />
            )}
            renderOption={(props, option) => {
              const { key, ...otherProps } = props;
              return (
                <Box
                  component="li"
                  key={key}
                  {...otherProps}
                  sx={{ display: 'flex', justifyContent: 'space-between', gap: 2 }}
                >
                  <Typography variant="body2" sx={{ fontWeight: 600 }}>
                    {option.secid}
                  </Typography>
                  <Typography variant="caption" sx={{ color: 'text.secondary' }}>
                    {option.shortname}
                  </Typography>
                </Box>
              );
            }}
          />
        </Grid>

        <Grid size={{ xs: 12, sm: 5 }}>
          <Autocomplete
            options={instruments.filter((i) => i.secid !== symbol1?.secid)}
            getOptionLabel={(option) => `${option.secid} - ${option.shortname}`}
            value={symbol2}
            onChange={(_, newValue) => setSymbol2(newValue)}
            loading={loadingInstruments}
            disabled={loadingInstruments}
            renderInput={(params) => (
              <TextField
                {...params}
                label="Symbol 2"
                placeholder={loadingInstruments ? "Loading..." : "Search..."}
                size="small"
                fullWidth
              />
            )}
            renderOption={(props, option) => {
              const { key, ...otherProps } = props;
              return (
                <Box
                  component="li"
                  key={key}
                  {...otherProps}
                  sx={{ display: 'flex', justifyContent: 'space-between', gap: 2 }}
                >
                  <Typography variant="body2" sx={{ fontWeight: 600 }}>
                    {option.secid}
                  </Typography>
                  <Typography variant="caption" sx={{ color: 'text.secondary' }}>
                    {option.shortname}
                  </Typography>
                </Box>
              );
            }}
          />
        </Grid>

        <Grid size={{ xs: 12, sm: 2 }}>
          <Button
            variant="contained"
            fullWidth
            onClick={handleAnalyze}
            disabled={analyzeMutation.isPending || !symbol1 || !symbol2}
            startIcon={
              analyzeMutation.isPending ? (
                <CircularProgress size={18} color="inherit" />
              ) : (
                <SearchIcon />
              )
            }
            sx={{ height: 40 }}
          >
            Analyze
          </Button>
        </Grid>
      </Grid>

      {error && (
        <Alert severity="error" sx={{ mt: 2 }} onClose={() => setError(null)}>
          {error}
        </Alert>
      )}

      {analyzeMutation.isSuccess && analyzeMutation.data && (
        <Box
          sx={{
            mt: 3,
            p: 2,
            borderRadius: 2,
            background: alpha(theme.palette.success.main, 0.1),
            border: `1px solid ${alpha(theme.palette.success.main, 0.3)}`,
          }}
        >
          <Typography variant="subtitle2" sx={{ color: 'success.main', mb: 1 }}>
            ✓ Analysis Complete - {analyzeMutation.data.data.symbol1}/{analyzeMutation.data.data.symbol2}
          </Typography>
          <Grid container spacing={2}>
            <Grid size={{ xs: 6, sm: 3 }}>
              <Typography variant="caption" sx={{ color: 'text.secondary' }}>
                Correlation
              </Typography>
              <Typography variant="body2" sx={{ fontWeight: 600 }}>
                {(analyzeMutation.data.data.correlation * 100).toFixed(1)}%
              </Typography>
            </Grid>
            <Grid size={{ xs: 6, sm: 3 }}>
              <Typography variant="caption" sx={{ color: 'text.secondary' }}>
                Cointegrated
              </Typography>
              <Typography
                variant="body2"
                sx={{
                  fontWeight: 600,
                  color: analyzeMutation.data.data.is_cointegrated ? 'success.main' : 'error.main',
                }}
              >
                {analyzeMutation.data.data.is_cointegrated ? 'Yes' : 'No'}
              </Typography>
            </Grid>
            <Grid size={{ xs: 6, sm: 3 }}>
              <Typography variant="caption" sx={{ color: 'text.secondary' }}>
                Z-Score
              </Typography>
              <Typography variant="body2" sx={{ fontWeight: 600 }}>
                {analyzeMutation.data.data.current_zscore.toFixed(4)}
              </Typography>
            </Grid>
            <Grid size={{ xs: 6, sm: 3 }}>
              <Typography variant="caption" sx={{ color: 'text.secondary' }}>
                Half-Life
              </Typography>
              <Typography variant="body2" sx={{ fontWeight: 600 }}>
                {analyzeMutation.data.data.half_life < 999
                  ? `${analyzeMutation.data.data.half_life.toFixed(1)} days`
                  : '∞'}
              </Typography>
            </Grid>
          </Grid>
        </Box>
      )}

      {/* Quick Add Suggestions */}
      <Box sx={{ mt: 3 }}>
        <Typography variant="caption" sx={{ color: 'text.secondary', display: 'block', mb: 1 }}>
          Popular Pairs (click to analyze directly)
        </Typography>
        <Box sx={{ display: 'flex', gap: 1, flexWrap: 'wrap' }}>
          {[
            ['SBER', 'SBERP'],
            ['GAZP', 'ROSN'],
            ['LKOH', 'ROSN'],
            ['VTBR', 'SBER'],
            ['GMKN', 'NLMK'],
          ].map(([s1, s2]) => (
            <Button
              key={`${s1}-${s2}`}
              variant="outlined"
              size="small"
              disabled={analyzeMutation.isPending}
              startIcon={analyzeMutation.isPending ? <CircularProgress size={14} /> : <AddIcon />}
              onClick={() => handleQuickAdd(s1, s2)}
              sx={{ fontSize: '0.75rem' }}
            >
              {s1}/{s2}
            </Button>
          ))}
        </Box>
      </Box>

      {/* Success notification */}
      <Snackbar
        open={!!successMessage}
        autoHideDuration={3000}
        onClose={() => setSuccessMessage(null)}
        message={successMessage}
      />
    </Paper>
  );
}
