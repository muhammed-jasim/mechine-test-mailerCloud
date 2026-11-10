import React, { useState } from 'react';
import styled from 'styled-components';
import {
  Dialog,
  DialogTitle,
  DialogContent,
  DialogActions,
  TextField,
  Button,
  Alert,
  IconButton,
  Tooltip,
} from '@mui/material';
import { Close as CloseIcon, Autorenew as AutorenewIcon } from '@mui/icons-material';
import { submitForm } from '../services/api';

const InputGroup = styled.div`
  display: flex;
  flex-direction: column;
  gap: 16px;
  margin-top: 12px;
`;

const KeyRow = styled.div`
  display: flex;
  gap: 8px;
  align-items: center;
`;

export default function SubmissionModal({ open, onClose, onSuccess }) {
  const [formId, setFormId] = useState('contact-form');
  const [email, setEmail] = useState('user@example.com');
  const [idempotencyKey, setIdempotencyKey] = useState(`key-${Date.now().toString().slice(-6)}`);
  const [jsonData, setJsonData] = useState('{\n  "name": "Jane Doe",\n  "message": "Interested in demo"\n}');
  const [submitting, setSubmitting] = useState(false);
  const [statusMessage, setStatusMessage] = useState(null);

  const generateNewKey = () => {
    setIdempotencyKey(`key-${Math.random().toString(36).substring(2, 9)}`);
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    setSubmitting(true);
    setStatusMessage(null);

    let parsedData = {};
    if (jsonData.trim()) {
      try {
        parsedData = JSON.parse(jsonData);
      } catch (err) {
        setStatusMessage({ type: 'error', text: 'Data must be valid JSON: ' + err.message });
        setSubmitting(false);
        return;
      }
    }

    try {
      const res = await submitForm({
        form_id: formId,
        idempotency_key: idempotencyKey,
        email: email,
        data: parsedData,
      });

      if (res.is_duplicate) {
        setStatusMessage({
          type: 'warning',
          text: `Duplicate idempotency key detected! Returning existing submission #${res.id}. No duplicate was created and no Kafka event was published.`,
        });
      } else {
        setStatusMessage({
          type: 'success',
          text: `Successfully created submission #${res.id}! Kafka event published to topic 'submission-events'.`,
        });
      }

      if (onSuccess) onSuccess();
    } catch (err) {
      const errorMsg =
        err.response?.data?.email?.[0] ||
        err.response?.data?.form_id?.[0] ||
        err.response?.data?.idempotency_key?.[0] ||
        err.message ||
        'Error submitting form';
      setStatusMessage({ type: 'error', text: errorMsg });
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <Dialog open={open} onClose={onClose} maxWidth="sm" fullWidth>
      <DialogTitle sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', pb: 1 }}>
        <span>Test Form Submission</span>
        <IconButton size="small" onClick={onClose}>
          <CloseIcon fontSize="small" />
        </IconButton>
      </DialogTitle>

      <form onSubmit={handleSubmit}>
        <DialogContent dividers>
          {statusMessage && (
            <Alert severity={statusMessage.type} sx={{ mb: 2 }}>
              {statusMessage.text}
            </Alert>
          )}

          <InputGroup>
            <TextField
              label="Form ID"
              value={formId}
              onChange={(e) => setFormId(e.target.value)}
              required
              fullWidth
              size="small"
              helperText="E.g., contact-form, newsletter, signup"
            />

            <TextField
              label="Email"
              type="email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              required
              fullWidth
              size="small"
              helperText="Must be a valid email format"
            />

            <KeyRow>
              <TextField
                label="Idempotency Key"
                value={idempotencyKey}
                onChange={(e) => setIdempotencyKey(e.target.value)}
                required
                fullWidth
                size="small"
                helperText="Send with same key to test duplicate idempotency rejection"
              />
              <Tooltip title="Generate Random Key">
                <Button
                  variant="outlined"
                  size="small"
                  onClick={generateNewKey}
                  sx={{ minWidth: '40px', px: 1, borderColor: '#cbd5e1', color: '#64748b' }}
                >
                  <AutorenewIcon fontSize="small" />
                </Button>
              </Tooltip>
            </KeyRow>

            <TextField
              label="Payload Data (JSON)"
              value={jsonData}
              onChange={(e) => setJsonData(e.target.value)}
              multiline
              rows={4}
              fullWidth
              size="small"
              placeholder="{}"
            />
          </InputGroup>
        </DialogContent>

        <DialogActions sx={{ p: 2 }}>
          <Button onClick={onClose} sx={{ color: '#64748b' }}>
            Close
          </Button>
          <Button
            type="submit"
            variant="contained"
            disabled={submitting}
            sx={{
              backgroundColor: '#288474',
              '&:hover': { backgroundColor: '#216d60' },
            }}
          >
            {submitting ? 'Submitting...' : 'Submit via API'}
          </Button>
        </DialogActions>
      </form>
    </Dialog>
  );
}

