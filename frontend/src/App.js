import React, { useState } from 'react';
import styled, { createGlobalStyle } from 'styled-components';
import { ThemeProvider, createTheme } from '@mui/material/styles';
import CssBaseline from '@mui/material/CssBaseline';

import Sidebar from './components/Sidebar';
import Overview from './pages/Overview';
import FormsPage from './pages/FormsPage';
import SubmissionsPage from './pages/SubmissionsPage';
import DuplicatesPage from './pages/DuplicatesPage';
import AnalyticsPage from './pages/AnalyticsPage';
import SubmissionModal from './components/SubmissionModal';

const GlobalStyle = createGlobalStyle`
  body {
    background-color: #f8fafc;
    color: #0f172a;
    font-family: 'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
    margin: 0;
    padding: 0;
    -webkit-font-smoothing: antialiased;
  }
`;

const theme = createTheme({
  palette: {
    primary: {
      main: '#288474',
      light: '#eef7f5',
      dark: '#216d60',
      contrastText: '#ffffff',
    },
    background: {
      default: '#f8fafc',
      paper: '#ffffff',
    },
    text: {
      primary: '#0f172a',
      secondary: '#64748b',
    },
  },
  typography: {
    fontFamily: "'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif",
    button: {
      textTransform: 'none',
      fontWeight: 600,
    },
  },
  shape: {
    borderRadius: 8,
  },
});

const Layout = styled.div`
  display: flex;
  min-height: 100vh;
`;

const MainContent = styled.main`
  flex: 1;
  padding: 32px 40px;
  max-width: 1400px;
  margin: 0 auto;
  width: calc(100% - 250px);

  @media (max-width: 768px) {
    padding: 20px 16px;
    width: 100%;
  }
`;

export default function App() {
  const [currentTab, setTab] = useState('overview');
  const [selectedFormFilter, setSelectedFormFilter] = useState('');
  const [isSubmitModalOpen, setIsSubmitModalOpen] = useState(false);
  const [refreshTrigger, setRefreshTrigger] = useState(0);

  const handleViewSubmissionsForForm = (formId) => {
    setSelectedFormFilter(formId);
    setTab('submissions');
  };

  const handleSubmissionSuccess = () => {
    setRefreshTrigger((prev) => prev + 1);
  };

  return (
    <ThemeProvider theme={theme}>
      <CssBaseline />
      <GlobalStyle />
      <Layout>
        <Sidebar
          currentTab={currentTab}
          setTab={(tab) => {
            if (tab !== 'submissions') {
              setSelectedFormFilter('');
            }
            setTab(tab);
          }}
          onOpenSubmitModal={() => setIsSubmitModalOpen(true)}
        />

        <MainContent>
          {currentTab === 'overview' && (
            <Overview
              key={`overview-${refreshTrigger}`}
              onSelectForm={handleViewSubmissionsForForm}
              onNavigateToDuplicates={() => setTab('duplicates')}
            />
          )}

          {currentTab === 'forms' && (
            <FormsPage
              key={`forms-${refreshTrigger}`}
              onViewSubmissions={handleViewSubmissionsForForm}
            />
          )}

          {currentTab === 'submissions' && (
            <SubmissionsPage
              key={`submissions-${refreshTrigger}-${selectedFormFilter}`}
              initialFormId={selectedFormFilter}
              onClearFormFilter={() => setSelectedFormFilter('')}
            />
          )}

          {currentTab === 'duplicates' && (
            <DuplicatesPage key={`duplicates-${refreshTrigger}`} />
          )}

          {currentTab === 'analytics' && (
            <AnalyticsPage key={`analytics-${refreshTrigger}`} />
          )}
        </MainContent>

        <SubmissionModal
          open={isSubmitModalOpen}
          onClose={() => setIsSubmitModalOpen(false)}
          onSuccess={handleSubmissionSuccess}
        />
      </Layout>
    </ThemeProvider>
  );
}
