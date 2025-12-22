import { Box, Typography, Grid, Paper, TextField, Divider, Chip, alpha, useTheme } from '@mui/material';
import { useQuery } from '@tanstack/react-query';
import { api } from '../api/client';

export default function Settings() {
  const theme = useTheme();

  const { data: settingsData, isLoading } = useQuery({
    queryKey: ['settings'],
    queryFn: () => api.getSettings(),
  });

  const settings = settingsData?.data;

  return (
    <Box>
      {/* Header */}
      <Box sx={{ mb: 3 }}>
        <Typography variant="h5" sx={{ fontWeight: 700, mb: 1 }}>
          Settings
        </Typography>
        <Typography variant="body2" sx={{ color: 'text.secondary' }}>
          Trading parameters and system configuration
        </Typography>
      </Box>

      <Grid container spacing={3}>
        {/* Trading Parameters */}
        <Grid size={{ xs: 12, md: 6 }}>
          <Paper sx={{ p: 3 }}>
            <Typography variant="h6" sx={{ fontWeight: 600, mb: 3 }}>
              Trading Parameters
            </Typography>

            <Box sx={{ display: 'flex', flexDirection: 'column', gap: 2.5 }}>
              <TextField
                label="Entry Threshold (Z-Score)"
                value={settings?.entry_threshold ?? 2.0}
                InputProps={{ readOnly: true }}
                size="small"
                helperText="Z-Score threshold for entering positions"
                fullWidth
              />

              <TextField
                label="Exit Threshold (Z-Score)"
                value={settings?.exit_threshold ?? 0.0}
                InputProps={{ readOnly: true }}
                size="small"
                helperText="Z-Score threshold for exiting positions"
                fullWidth
              />

              <TextField
                label="Stop Loss Threshold (Z-Score)"
                value={settings?.stop_loss_threshold ?? 3.0}
                InputProps={{ readOnly: true }}
                size="small"
                helperText="Z-Score threshold for stop loss"
                fullWidth
              />

              <Divider sx={{ my: 1 }} />

              <TextField
                label="Lookback Period"
                value={settings?.lookback_period ?? 60}
                InputProps={{ readOnly: true }}
                size="small"
                helperText="Number of periods for analysis"
                fullWidth
              />

              <TextField
                label="Spread Window"
                value={settings?.spread_window ?? 20}
                InputProps={{ readOnly: true }}
                size="small"
                helperText="Rolling window for Z-Score calculation"
                fullWidth
              />
            </Box>
          </Paper>
        </Grid>

        {/* System Configuration */}
        <Grid size={{ xs: 12, md: 6 }}>
          <Paper sx={{ p: 3 }}>
            <Typography variant="h6" sx={{ fontWeight: 600, mb: 3 }}>
              System Configuration
            </Typography>

            <Box sx={{ display: 'flex', flexDirection: 'column', gap: 2.5 }}>
              <TextField
                label="Candle Interval"
                value={
                  settings?.candle_interval === 24
                    ? 'Daily'
                    : settings?.candle_interval === 60
                      ? 'Hourly'
                      : settings?.candle_interval === 1
                        ? '1 Minute'
                        : `${settings?.candle_interval ?? 24} minutes`
                }
                InputProps={{ readOnly: true }}
                size="small"
                helperText="OHLCV data interval for analysis"
                fullWidth
              />

              <TextField
                label="Analysis Interval"
                value={`${settings?.analysis_interval ?? 300} seconds`}
                InputProps={{ readOnly: true }}
                size="small"
                helperText="How often the screener runs analysis"
                fullWidth
              />

              <Divider sx={{ my: 1 }} />

              <Box>
                <Typography variant="body2" sx={{ color: 'text.secondary', mb: 1 }}>
                  Market Hours (Moscow Time)
                </Typography>
                <Box sx={{ display: 'flex', gap: 1 }}>
                  <Chip label="Open: 10:00" variant="outlined" size="small" />
                  <Chip label="Close: 18:50" variant="outlined" size="small" />
                </Box>
              </Box>
            </Box>
          </Paper>

          {/* Signal Strength Thresholds */}
          <Paper sx={{ p: 3, mt: 3 }}>
            <Typography variant="h6" sx={{ fontWeight: 600, mb: 3 }}>
              Signal Strength Thresholds
            </Typography>

            <Grid container spacing={2}>
              <Grid size={4}>
                <Box
                  sx={{
                    p: 2,
                    borderRadius: 2,
                    textAlign: 'center',
                    background: alpha(theme.palette.error.main, 0.1),
                    border: `1px solid ${alpha(theme.palette.error.main, 0.3)}`,
                  }}
                >
                  <Typography variant="h6" sx={{ fontWeight: 700, color: 'error.main' }}>
                    ≥ 3.0
                  </Typography>
                  <Typography variant="caption" sx={{ color: 'text.secondary' }}>
                    Strong
                  </Typography>
                </Box>
              </Grid>
              <Grid size={4}>
                <Box
                  sx={{
                    p: 2,
                    borderRadius: 2,
                    textAlign: 'center',
                    background: alpha(theme.palette.warning.main, 0.1),
                    border: `1px solid ${alpha(theme.palette.warning.main, 0.3)}`,
                  }}
                >
                  <Typography variant="h6" sx={{ fontWeight: 700, color: 'warning.main' }}>
                    ≥ 2.5
                  </Typography>
                  <Typography variant="caption" sx={{ color: 'text.secondary' }}>
                    Moderate
                  </Typography>
                </Box>
              </Grid>
              <Grid size={4}>
                <Box
                  sx={{
                    p: 2,
                    borderRadius: 2,
                    textAlign: 'center',
                    background: alpha(theme.palette.info.main, 0.1),
                    border: `1px solid ${alpha(theme.palette.info.main, 0.3)}`,
                  }}
                >
                  <Typography variant="h6" sx={{ fontWeight: 700, color: 'info.main' }}>
                    ≥ 2.0
                  </Typography>
                  <Typography variant="caption" sx={{ color: 'text.secondary' }}>
                    Weak
                  </Typography>
                </Box>
              </Grid>
            </Grid>
          </Paper>
        </Grid>

        {/* Strategy Overview */}
        <Grid size={12}>
          <Paper sx={{ p: 3 }}>
            <Typography variant="h6" sx={{ fontWeight: 600, mb: 2 }}>
              Pair Trading Strategy Overview
            </Typography>
            <Grid container spacing={3}>
              <Grid size={{ xs: 12, md: 6 }}>
                <Typography variant="subtitle2" sx={{ mb: 1 }}>
                  Entry Conditions
                </Typography>
                <Box
                  sx={{
                    p: 2,
                    borderRadius: 2,
                    background: alpha(theme.palette.background.default, 0.5),
                  }}
                >
                  <Typography variant="body2" sx={{ mb: 1 }}>
                    <strong>Long Spread:</strong> Z-Score ≤ -{settings?.entry_threshold ?? 2.0}
                  </Typography>
                  <Typography variant="caption" sx={{ color: 'text.secondary', display: 'block' }}>
                    Buy Symbol1, Sell Symbol2. Expect spread to increase toward mean.
                  </Typography>
                  <Divider sx={{ my: 1.5 }} />
                  <Typography variant="body2" sx={{ mb: 1 }}>
                    <strong>Short Spread:</strong> Z-Score ≥ +{settings?.entry_threshold ?? 2.0}
                  </Typography>
                  <Typography variant="caption" sx={{ color: 'text.secondary', display: 'block' }}>
                    Sell Symbol1, Buy Symbol2. Expect spread to decrease toward mean.
                  </Typography>
                </Box>
              </Grid>
              <Grid size={{ xs: 12, md: 6 }}>
                <Typography variant="subtitle2" sx={{ mb: 1 }}>
                  Exit Conditions
                </Typography>
                <Box
                  sx={{
                    p: 2,
                    borderRadius: 2,
                    background: alpha(theme.palette.background.default, 0.5),
                  }}
                >
                  <Typography variant="body2" sx={{ mb: 1 }}>
                    <strong>Take Profit:</strong> Z-Score crosses {settings?.exit_threshold ?? 0}
                  </Typography>
                  <Typography variant="caption" sx={{ color: 'text.secondary', display: 'block' }}>
                    Mean reversion complete. Close position and take profit.
                  </Typography>
                  <Divider sx={{ my: 1.5 }} />
                  <Typography variant="body2" sx={{ mb: 1 }}>
                    <strong>Stop Loss:</strong> |Z-Score| ≥ {settings?.stop_loss_threshold ?? 3.0}
                  </Typography>
                  <Typography variant="caption" sx={{ color: 'text.secondary', display: 'block' }}>
                    Spread diverging further. Close position to limit losses.
                  </Typography>
                </Box>
              </Grid>
            </Grid>
          </Paper>
        </Grid>

        {/* Pair Criteria */}
        <Grid size={12}>
          <Paper sx={{ p: 3 }}>
            <Typography variant="h6" sx={{ fontWeight: 600, mb: 2 }}>
              Tradeable Pair Criteria
            </Typography>
            <Grid container spacing={2}>
              <Grid size={{ xs: 6, sm: 3 }}>
                <Box sx={{ textAlign: 'center', p: 2 }}>
                  <Typography variant="h5" sx={{ fontWeight: 700, color: 'primary.main' }}>
                    ≥ 70%
                  </Typography>
                  <Typography variant="body2" sx={{ color: 'text.secondary' }}>
                    Minimum Correlation
                  </Typography>
                </Box>
              </Grid>
              <Grid size={{ xs: 6, sm: 3 }}>
                <Box sx={{ textAlign: 'center', p: 2 }}>
                  <Typography variant="h5" sx={{ fontWeight: 700, color: 'success.main' }}>
                    ≤ 0.05
                  </Typography>
                  <Typography variant="body2" sx={{ color: 'text.secondary' }}>
                    Cointegration p-value
                  </Typography>
                </Box>
              </Grid>
              <Grid size={{ xs: 6, sm: 3 }}>
                <Box sx={{ textAlign: 'center', p: 2 }}>
                  <Typography variant="h5" sx={{ fontWeight: 700, color: 'warning.main' }}>
                    ≤ 30 days
                  </Typography>
                  <Typography variant="body2" sx={{ color: 'text.secondary' }}>
                    Max Half-Life
                  </Typography>
                </Box>
              </Grid>
              <Grid size={{ xs: 6, sm: 3 }}>
                <Box sx={{ textAlign: 'center', p: 2 }}>
                  <Typography variant="h5" sx={{ fontWeight: 700, color: 'secondary.main' }}>
                    {'< 0.5'}
                  </Typography>
                  <Typography variant="body2" sx={{ color: 'text.secondary' }}>
                    Max Hurst Exponent
                  </Typography>
                </Box>
              </Grid>
            </Grid>
          </Paper>
        </Grid>
      </Grid>
    </Box>
  );
}

