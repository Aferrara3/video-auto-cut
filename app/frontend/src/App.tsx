import * as React from 'react';
import { BrowserRouter as Router, Routes, Route, Navigate } from 'react-router-dom';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { ThemeProvider, createTheme } from '@mui/material/styles';
import Layout from './components/Layout';
import BRollLibrary from './pages/BRollLibrary';
import StoryStudio from './pages/StoryStudio';
import ActionStudio from './pages/ActionStudio';
import { ColorModeContext } from './context/ColorModeContext';
import './App.css';

const queryClient = new QueryClient();

function App() {
  const [mode, setMode] = React.useState<'light' | 'dark'>('dark'); // Default to dark for "sexy" look
  
  const colorMode = React.useMemo(
    () => ({
      toggleColorMode: () => {
        setMode((prevMode) => (prevMode === 'light' ? 'dark' : 'light'));
      },
      mode,
    }),
    [mode],
  );

  const theme = React.useMemo(
    () =>
      createTheme({
        palette: {
          mode,
          ...(mode === 'dark' ? {
             primary: {
               main: '#90caf9',
             },
             secondary: {
               main: '#f48fb1',
             },
             background: {
               default: '#121212',
               paper: '#1e1e1e',
             }
          } : {
             primary: {
               main: '#1976d2',
             },
          }),
        },
      }),
    [mode],
  );

  return (
    <ColorModeContext.Provider value={colorMode}>
      <QueryClientProvider client={queryClient}>
        <ThemeProvider theme={theme}>
          <Router>
            <Routes>
              <Route path="/" element={<Layout />}>
                <Route index element={<Navigate to="/broll" replace />} />
                <Route path="broll" element={<BRollLibrary />} />
                <Route path="story" element={<StoryStudio />} />
                <Route path="action" element={<ActionStudio />} />
              </Route>
            </Routes>
          </Router>
        </ThemeProvider>
      </QueryClientProvider>
    </ColorModeContext.Provider>
  );
}

export default App;
