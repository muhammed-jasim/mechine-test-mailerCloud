from django.test import TestCase
from django.urls import reverse
from rest_framework.test import APIClient
from rest_framework import status
from unittest.mock import patch

from .models import Submission, DuplicateLog


class SubmissionAPITests(TestCase):
    def setUp(self):
        self.client = APIClient()

    @patch('submissions.views.publish_submission_event')
    def test_create_valid_submission(self, mock_publish):
        """Test submitting valid data creates a record and triggers Kafka publish."""
        payload = {
            "form_id": "contact-form",
            "idempotency_key": "test-key-001",
            "email": "user@example.com",
            "data": {"name": "Alice", "message": "Hello world"}
        }
        response = self.client.post('/api/submissions/', payload, format='json')
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data['form_id'], "contact-form")
        self.assertEqual(response.data['email'], "user@example.com")
        self.assertEqual(response.data['idempotency_key'], "test-key-001")
        self.assertFalse(response.data['is_duplicate'])

        # Check database
        self.assertEqual(Submission.objects.count(), 1)
        sub = Submission.objects.get(idempotency_key="test-key-001")
        self.assertEqual(sub.email, "user@example.com")
        self.assertEqual(sub.data, {"name": "Alice", "message": "Hello world"})

        # Verify Kafka publisher called once
        mock_publish.assert_called_once()

    @patch('submissions.views.publish_submission_event')
    def test_duplicate_idempotency_key_returns_existing_record(self, mock_publish):
        """
        Duplicate idempotency keys should return the existing record (200 OK)
        without creating a new record and without re-publishing to Kafka.
        """
        payload1 = {
            "form_id": "feedback-form",
            "idempotency_key": "idemp-xyz",
            "email": "user1@example.com",
            "data": {"rating": 5}
        }
        res1 = self.client.post('/api/submissions/', payload1, format='json')
        self.assertEqual(res1.status_code, status.HTTP_201_CREATED)
        first_id = res1.data['id']
        self.assertEqual(mock_publish.call_count, 1)

        # Send same idempotency_key with different email/data
        payload2 = {
            "form_id": "feedback-form",
            "idempotency_key": "idemp-xyz",
            "email": "different@example.com",
            "data": {"rating": 1}
        }
        res2 = self.client.post('/api/submissions/', payload2, format='json')
        self.assertEqual(res2.status_code, status.HTTP_200_OK)
        self.assertEqual(res2.data['id'], first_id)
        self.assertEqual(res2.data['email'], "user1@example.com")
        self.assertTrue(res2.data['is_duplicate'])

        # Total in DB should still be 1
        self.assertEqual(Submission.objects.count(), 1)

        # Duplicate log must be recorded
        self.assertEqual(DuplicateLog.objects.count(), 1)
        log = DuplicateLog.objects.first()
        self.assertEqual(log.idempotency_key, "idemp-xyz")
        self.assertEqual(log.attempted_email, "different@example.com")
        self.assertEqual(log.original_submission_id, first_id)

        # Kafka publish should NOT be called a second time
        self.assertEqual(mock_publish.call_count, 1)

    def test_invalid_email_returns_400(self):
        """Invalid email formats must return 400 Bad Request."""
        invalid_emails = ["notanemail", "user@", "@domain.com", ""]
        for bad_email in invalid_emails:
            payload = {
                "form_id": "contact-form",
                "idempotency_key": f"key-{bad_email}",
                "email": bad_email,
                "data": {}
            }
            res = self.client.post('/api/submissions/', payload, format='json')
            self.assertEqual(res.status_code, status.HTTP_400_BAD_REQUEST)
            self.assertIn('email', res.data)

    def test_missing_form_id_returns_400(self):
        """Missing or blank form_id must return 400 Bad Request."""
        payload_missing = {
            "idempotency_key": "key-missing-form",
            "email": "valid@example.com",
            "data": {}
        }
        res = self.client.post('/api/submissions/', payload_missing, format='json')
        self.assertEqual(res.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('form_id', res.data)

        payload_blank = {
            "form_id": "   ",
            "idempotency_key": "key-blank-form",
            "email": "valid@example.com",
            "data": {}
        }
        res2 = self.client.post('/api/submissions/', payload_blank, format='json')
        self.assertEqual(res2.status_code, status.HTTP_400_BAD_REQUEST)

    def test_get_submissions_by_form_pagination(self):
        """
        GET /api/forms/{form_id}/submissions/
        Should return 10 records per page.
        """
        # Create 15 submissions for 'survey-form' and 3 for 'contact-form'
        for i in range(15):
            Submission.objects.create(
                form_id="survey-form",
                idempotency_key=f"survey-key-{i}",
                email=f"survey{i}@example.com",
                data={"question": i}
            )
        for i in range(3):
            Submission.objects.create(
                form_id="contact-form",
                idempotency_key=f"contact-key-{i}",
                email=f"contact{i}@example.com",
                data={"inquiry": i}
            )

        # Page 1 for survey-form
        res_p1 = self.client.get('/api/forms/survey-form/submissions/')
        self.assertEqual(res_p1.status_code, status.HTTP_200_OK)
        self.assertEqual(res_p1.data['count'], 15)
        self.assertEqual(len(res_p1.data['results']), 10)
        self.assertIsNotNone(res_p1.data['next'])

        # Page 2 for survey-form
        res_p2 = self.client.get('/api/forms/survey-form/submissions/?page=2')
        self.assertEqual(res_p2.status_code, status.HTTP_200_OK)
        self.assertEqual(len(res_p2.data['results']), 5)
        self.assertIsNone(res_p2.data['next'])

        # Check contact-form isolation
        res_contact = self.client.get('/api/forms/contact-form/submissions/')
        self.assertEqual(res_contact.data['count'], 3)
        self.assertEqual(len(res_contact.data['results']), 3)

    def test_root_path_compatibility(self):
        """Verify routes work both with and without /api/ prefix."""
        payload = {
            "form_id": "root-form",
            "idempotency_key": "root-key-1",
            "email": "root@example.com",
            "data": {}
        }
        res = self.client.post('/submissions/', payload, format='json')
        self.assertIn(res.status_code, [status.HTTP_201_CREATED, status.HTTP_200_OK])

        res_get = self.client.get('/forms/root-form/submissions/')
        self.assertEqual(res_get.status_code, status.HTTP_200_OK)
        self.assertEqual(res_get.data['count'], 1)

    def test_analytics_and_forms_endpoints(self):
        """Test supporting analytics and forms summary endpoints."""
        Submission.objects.create(
            form_id="test-form-a",
            idempotency_key="key-a",
            email="a@example.com",
            data={"score": 10}
        )
        Submission.objects.create(
            form_id="test-form-b",
            idempotency_key="key-b",
            email="b@example.com",
            data={"score": 20}
        )

        # Forms summary
        res_forms = self.client.get('/api/forms/')
        self.assertEqual(res_forms.status_code, status.HTTP_200_OK)
        self.assertEqual(len(res_forms.data), 2)

        # Overview
        res_overview = self.client.get('/api/analytics/overview/')
        self.assertEqual(res_overview.status_code, status.HTTP_200_OK)
        self.assertEqual(res_overview.data['total_submissions'], 2)
        self.assertEqual(res_overview.data['total_forms'], 2)
        self.assertEqual(len(res_overview.data['form_distribution']), 2)

        # Hourly analytics
        res_hourly = self.client.get('/api/analytics/hourly/')
        self.assertEqual(res_hourly.status_code, status.HTTP_200_OK)
