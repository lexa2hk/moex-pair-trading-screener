import { createTheme, alpha } from '@mui/material/styles';

// Dark theme inspired by trading terminals with a distinctive aesthetic
const theme = createTheme({
  palette: {
    mode: 'dark',
    primary: {
      main: '#00E5FF',
      light: '#6EFFFF',
      dark: '#00B2CC',
      contrastText: '#0A0F1A',
    },
    secondary: {
      main: '#FF6B35',
      light: '#FF9A6B',
      dark: '#CC4400',
    },
    success: {
      main: '#00E676',
      light: '#66FFA6',
      dark: '#00B248',
    },
    error: {
      main: '#FF5252',
      light: '#FF8A80',
      dark: '#D32F2F',
    },
    warning: {
      main: '#FFD740',
      light: '#FFEA00',
      dark: '#FFA000',
    },
    background: {
      default: '#0A0F1A',
      paper: '#111827',
    },
    text: {
      primary: '#E8ECF4',
      secondary: '#94A3B8',
    },
    divider: alpha('#00E5FF', 0.12),
  },
  typography: {
    fontFamily: '"JetBrains Mono", "Fira Code", "SF Mono", "Consolas", monospace',
    h1: {
      fontFamily: '"Outfit", "Inter", sans-serif',
      fontWeight: 700,
      letterSpacing: '-0.02em',
    },
    h2: {
      fontFamily: '"Outfit", "Inter", sans-serif',
      fontWeight: 600,
      letterSpacing: '-0.01em',
    },
    h3: {
      fontFamily: '"Outfit", "Inter", sans-serif',
      fontWeight: 600,
    },
    h4: {
      fontFamily: '"Outfit", "Inter", sans-serif',
      fontWeight: 600,
    },
    h5: {
      fontFamily: '"Outfit", "Inter", sans-serif',
      fontWeight: 500,
    },
    h6: {
      fontFamily: '"Outfit", "Inter", sans-serif',
      fontWeight: 500,
    },
    subtitle1: {
      fontWeight: 500,
      letterSpacing: '0.01em',
    },
    body1: {
      fontSize: '0.9375rem',
      letterSpacing: '0.01em',
    },
    body2: {
      fontSize: '0.8125rem',
      letterSpacing: '0.01em',
    },
    button: {
      fontWeight: 600,
      letterSpacing: '0.03em',
      textTransform: 'none',
    },
    overline: {
      fontWeight: 600,
      letterSpacing: '0.1em',
      fontSize: '0.6875rem',
    },
  },
  shape: {
    borderRadius: 12,
  },
  components: {
    MuiCssBaseline: {
      styleOverrides: {
        '@import': [
          "url('https://fonts.googleapis.com/css2?family=JetBrains+Mono:wght@300;400;500;600;700&family=Outfit:wght@300;400;500;600;700;800&display=swap')",
        ],
        body: {
          backgroundImage: `
            radial-gradient(ellipse at 20% 0%, ${alpha('#00E5FF', 0.08)} 0%, transparent 50%),
            radial-gradient(ellipse at 80% 100%, ${alpha('#FF6B35', 0.06)} 0%, transparent 50%)
          `,
          backgroundAttachment: 'fixed',
          minHeight: '100vh',
        },
        '::-webkit-scrollbar': {
          width: '8px',
          height: '8px',
        },
        '::-webkit-scrollbar-track': {
          background: '#0A0F1A',
        },
        '::-webkit-scrollbar-thumb': {
          background: '#1E293B',
          borderRadius: '4px',
          '&:hover': {
            background: '#334155',
          },
        },
      },
    },
    MuiPaper: {
      styleOverrides: {
        root: {
          backgroundImage: 'none',
          border: `1px solid ${alpha('#00E5FF', 0.1)}`,
          boxShadow: `0 4px 24px ${alpha('#000', 0.4)}, inset 0 1px 0 ${alpha('#fff', 0.03)}`,
        },
      },
    },
    MuiCard: {
      styleOverrides: {
        root: {
          background: `linear-gradient(180deg, ${alpha('#111827', 0.95)} 0%, ${alpha('#0D1321', 0.98)} 100%)`,
          backdropFilter: 'blur(20px)',
        },
      },
    },
    MuiButton: {
      styleOverrides: {
        root: {
          borderRadius: 8,
          padding: '10px 24px',
          transition: 'all 0.2s ease-in-out',
        },
        contained: {
          boxShadow: `0 4px 14px ${alpha('#00E5FF', 0.25)}`,
          '&:hover': {
            boxShadow: `0 6px 20px ${alpha('#00E5FF', 0.35)}`,
            transform: 'translateY(-1px)',
          },
        },
        outlined: {
          borderWidth: '1.5px',
          '&:hover': {
            borderWidth: '1.5px',
            background: alpha('#00E5FF', 0.08),
          },
        },
      },
    },
    MuiChip: {
      styleOverrides: {
        root: {
          fontWeight: 600,
          letterSpacing: '0.02em',
        },
        colorSuccess: {
          background: alpha('#00E676', 0.15),
          color: '#00E676',
          border: `1px solid ${alpha('#00E676', 0.3)}`,
        },
        colorError: {
          background: alpha('#FF5252', 0.15),
          color: '#FF5252',
          border: `1px solid ${alpha('#FF5252', 0.3)}`,
        },
        colorWarning: {
          background: alpha('#FFD740', 0.15),
          color: '#FFD740',
          border: `1px solid ${alpha('#FFD740', 0.3)}`,
        },
      },
    },
    MuiTableCell: {
      styleOverrides: {
        root: {
          borderColor: alpha('#00E5FF', 0.08),
        },
        head: {
          fontWeight: 600,
          textTransform: 'uppercase',
          fontSize: '0.75rem',
          letterSpacing: '0.08em',
          color: '#94A3B8',
        },
      },
    },
    MuiTableRow: {
      styleOverrides: {
        root: {
          transition: 'background-color 0.15s ease',
          '&:hover': {
            backgroundColor: alpha('#00E5FF', 0.04),
          },
        },
      },
    },
    MuiTextField: {
      styleOverrides: {
        root: {
          '& .MuiOutlinedInput-root': {
            '& fieldset': {
              borderColor: alpha('#00E5FF', 0.2),
            },
            '&:hover fieldset': {
              borderColor: alpha('#00E5FF', 0.4),
            },
            '&.Mui-focused fieldset': {
              borderColor: '#00E5FF',
            },
          },
        },
      },
    },
    MuiSelect: {
      styleOverrides: {
        root: {
          '& .MuiOutlinedInput-notchedOutline': {
            borderColor: alpha('#00E5FF', 0.2),
          },
          '&:hover .MuiOutlinedInput-notchedOutline': {
            borderColor: alpha('#00E5FF', 0.4),
          },
          '&.Mui-focused .MuiOutlinedInput-notchedOutline': {
            borderColor: '#00E5FF',
          },
        },
      },
    },
    MuiDrawer: {
      styleOverrides: {
        paper: {
          background: `linear-gradient(180deg, ${alpha('#0D1321', 0.98)} 0%, ${alpha('#0A0F1A', 0.99)} 100%)`,
          borderRight: `1px solid ${alpha('#00E5FF', 0.1)}`,
        },
      },
    },
    MuiAppBar: {
      styleOverrides: {
        root: {
          background: alpha('#0A0F1A', 0.8),
          backdropFilter: 'blur(20px)',
          borderBottom: `1px solid ${alpha('#00E5FF', 0.1)}`,
          boxShadow: 'none',
        },
      },
    },
    MuiListItemButton: {
      styleOverrides: {
        root: {
          borderRadius: 8,
          margin: '4px 8px',
          '&.Mui-selected': {
            background: alpha('#00E5FF', 0.12),
            '&:hover': {
              background: alpha('#00E5FF', 0.16),
            },
            '&::before': {
              content: '""',
              position: 'absolute',
              left: 0,
              top: '50%',
              transform: 'translateY(-50%)',
              width: 3,
              height: '60%',
              borderRadius: '0 4px 4px 0',
              background: '#00E5FF',
            },
          },
        },
      },
    },
    MuiTooltip: {
      styleOverrides: {
        tooltip: {
          background: alpha('#1E293B', 0.95),
          backdropFilter: 'blur(10px)',
          border: `1px solid ${alpha('#00E5FF', 0.2)}`,
          borderRadius: 8,
          fontSize: '0.8125rem',
          padding: '8px 12px',
        },
      },
    },
    MuiLinearProgress: {
      styleOverrides: {
        root: {
          borderRadius: 4,
          height: 6,
          backgroundColor: alpha('#00E5FF', 0.1),
        },
        bar: {
          borderRadius: 4,
        },
      },
    },
  },
});

export default theme;

