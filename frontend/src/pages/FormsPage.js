import React, { useEffect, useState } from 'react';
import styled from 'styled-components';
import {
  Box,
  Typography,
  IconButton,
  Tooltip,
  CircularProgress,
  Button,
  Chip,
  Card,
  CardContent,
} from '@mui/material';
import {
  Refresh as RefreshIcon,
  Description as DescriptionIcon,
  ArrowForward as ArrowForwardIcon,
  EventNote as EventNoteIcon,
} from '@mui/icons-material';
import { getForms } from '../services/api';

const PageHeader = styled.div`
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 24px;
`;

const FormsGrid = styled.div`
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(320px, 1fr));
  gap: 20px;
`;

const StyledCard = styled(Card)`
  border-radius: 12px !important;
  border: 1px solid #f1f5f9 !important;
  box-shadow: 0 1px 3px rgba(0, 0, 0, 0.05) !important;
  transition: transform 0.15s ease, box-shadow 0.15s ease !important;

  &:hover {
    transform: translateY(-2px);
    box-shadow: 0 4px 12px rgba(0, 0, 0, 0.08) !important;
  }
`;

export default function FormsPage({ onViewSubmissions }) {
  const [forms, setForms] = useState([]);
  const [loading, setLoading] = useState(true);

  const fetchForms = async () => {
    try {
      setLoading(true);
      const data = await getForms();
      setForms(data);
    } catch (err) {
      console.error('Failed to load forms:', err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchForms();
  }, []);

  return (
    <div>
      <PageHeader>
        <div>
          <Typography variant="h5" sx={{ fontWeight: 700, color: '#0f172a' }}>
            Registered Forms
          </Typography>
          <Typography variant="body2" sx={{ color: '#64748b' }}>
            Browse active form endpoints and submission volumes
          </Typography>
        </div>
        <Tooltip title="Refresh forms">
          <IconButton onClick={fetchForms} sx={{ color: '#288474' }}>
            <RefreshIcon />
          </IconButton>
        </Tooltip>
      </PageHeader>

      {loading ? (
        <Box sx={{ display: 'flex', justifyContent: 'center', py: 8 }}>
          <CircularProgress sx={{ color: '#288474' }} />
        </Box>
      ) : forms.length === 0 ? (
        <Box
          sx={{
            textAlign: 'center',
            py: 8,
            backgroundColor: '#ffffff',
            borderRadius: '12px',
            border: '1px solid #f1f5f9',
          }}
        >
          <DescriptionIcon sx={{ fontSize: 48, color: '#cbd5e1', mb: 1 }} />
          <Typography variant="subtitle1" sx={{ color: '#64748b', fontWeight: 500 }}>
            No forms have received submissions yet.
          </Typography>
          <Typography variant="body2" sx={{ color: '#94a3b8', mt: 0.5 }}>
            Submit a test form to see it dynamically appear here.
          </Typography>
        </Box>
      ) : (
        <FormsGrid>
          {forms.map((form) => (
            <StyledCard key={form.form_id}>
              <CardContent sx={{ p: 3 }}>
                <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', mb: 2 }}>
                  <Box>
                    <Chip
                      label={form.form_id}
                      sx={{
                        backgroundColor: '#eef7f5',
                        color: '#288474',
                        fontWeight: 700,
                        fontSize: '13px',
                      }}
                    />
                  </Box>
                  <Typography variant="h5" sx={{ fontWeight: 700, color: '#0f172a' }}>
                    {form.submission_count.toLocaleString()}
                    <Typography component="span" variant="caption" sx={{ color: '#64748b', ml: 0.5 }}>
                      entries
                    </Typography>
                  </Typography>
                </Box>

                <Box sx={{ display: 'flex', flexDirection: 'column', gap: 1, my: 2 }}>
                  <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, color: '#64748b' }}>
                    <EventNoteIcon sx={{ fontSize: 16 }} />
                    <Typography variant="caption">
                      Last active: {form.last_submission ? new Date(form.last_submission).toLocaleString() : 'N/A'}
                    </Typography>
                  </Box>
                </Box>

                <Button
                  fullWidth
                  variant="outlined"
                  size="small"
                  endIcon={<ArrowForwardIcon />}
                  onClick={() => onViewSubmissions(form.form_id)}
                  sx={{
                    mt: 1,
                    borderColor: '#288474',
                    color: '#288474',
                    fontWeight: 600,
                    '&:hover': {
                      backgroundColor: '#eef7f5',
                      borderColor: '#288474',
                    },
                  }}
                >
                  View Form Submissions
                </Button>
              </CardContent>
            </StyledCard>
          ))}
        </FormsGrid>
      )}
    </div>
  );
}
