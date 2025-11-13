from django.test import TestCase, Client
from django.urls import reverse
from django.utils import timezone
from datetime import datetime
import json

from nutrition.models import NutritionEntry


class NutritionAPITestCase(TestCase):
    """Tests for Nutrition API endpoints"""

    def setUp(self):
        """Set up test data"""
        self.client = Client()

    def test_log_nutrition_success(self):
        """Test logging a nutrition entry successfully"""
        data = {
            'calories': '500',
            'fat': '20',
            'carbs': '50',
            'protein': '30',
            'date': '2025-10-28'
        }

        response = self.client.post(
            reverse('nutrition:log_nutrition'),
            data=data
        )

        self.assertEqual(response.status_code, 200)
        result = json.loads(response.content)
        self.assertTrue(result['success'])
        self.assertIn('logged successfully', result['message'])
        self.assertEqual(result['calories'], 500.0)
        self.assertEqual(result['fat'], 20.0)
        self.assertEqual(result['carbs'], 50.0)
        self.assertEqual(result['protein'], 30.0)

        # Verify entry was created
        entry = NutritionEntry.objects.get(id=result['entry_id'])
        self.assertEqual(entry.source, 'Manual')
        self.assertEqual(float(entry.calories), 500.0)
        self.assertEqual(float(entry.fat), 20.0)
        self.assertEqual(float(entry.carbs), 50.0)
        self.assertEqual(float(entry.protein), 30.0)

    def test_log_nutrition_with_decimal_values(self):
        """Test logging nutrition with decimal values"""
        data = {
            'calories': '523.5',
            'fat': '22.8',
            'carbs': '45.2',
            'protein': '35.1',
            'date': '2025-10-28'
        }

        response = self.client.post(
            reverse('nutrition:log_nutrition'),
            data=data
        )

        self.assertEqual(response.status_code, 200)
        result = json.loads(response.content)
        self.assertTrue(result['success'])
        self.assertEqual(result['calories'], 523.5)
        self.assertEqual(result['fat'], 22.8)

    def test_log_nutrition_missing_field(self):
        """Test logging nutrition with missing required field"""
        data = {
            'calories': '500',
            'fat': '20',
            # Missing carbs
            'protein': '30',
            'date': '2025-10-28'
        }

        response = self.client.post(
            reverse('nutrition:log_nutrition'),
            data=data
        )

        self.assertEqual(response.status_code, 400)
        result = json.loads(response.content)
        self.assertFalse(result['success'])
        self.assertIn('required', result['message'])

    def test_log_nutrition_non_numeric_value(self):
        """Test logging nutrition with non-numeric value"""
        data = {
            'calories': 'abc',  # Invalid
            'fat': '20',
            'carbs': '50',
            'protein': '30',
            'date': '2025-10-28'
        }

        response = self.client.post(
            reverse('nutrition:log_nutrition'),
            data=data
        )

        self.assertEqual(response.status_code, 400)
        result = json.loads(response.content)
        self.assertFalse(result['success'])
        self.assertIn('valid numbers', result['message'])

    def test_log_nutrition_negative_value(self):
        """Test logging nutrition with negative value"""
        data = {
            'calories': '-100',  # Negative
            'fat': '20',
            'carbs': '50',
            'protein': '30',
            'date': '2025-10-28'
        }

        response = self.client.post(
            reverse('nutrition:log_nutrition'),
            data=data
        )

        self.assertEqual(response.status_code, 400)
        result = json.loads(response.content)
        self.assertFalse(result['success'])
        self.assertIn('cannot be negative', result['message'])

    def test_log_nutrition_invalid_date_format(self):
        """Test logging nutrition with invalid date format"""
        data = {
            'calories': '500',
            'fat': '20',
            'carbs': '50',
            'protein': '30',
            'date': 'invalid-date'
        }

        response = self.client.post(
            reverse('nutrition:log_nutrition'),
            data=data
        )

        self.assertEqual(response.status_code, 400)
        result = json.loads(response.content)
        self.assertFalse(result['success'])
        self.assertIn('date format', result['message'])

    def test_log_nutrition_with_utc_date(self):
        """Test logging nutrition with date string"""
        data = {
            'calories': '600',
            'fat': '25',
            'carbs': '60',
            'protein': '40',
            'date': '2025-10-28'
        }

        response = self.client.post(
            reverse('nutrition:log_nutrition'),
            data=data
        )

        self.assertEqual(response.status_code, 200)
        result = json.loads(response.content)
        self.assertTrue(result['success'])

    def test_log_nutrition_with_zero_values(self):
        """Test logging nutrition with zero values (valid edge case)"""
        data = {
            'calories': '0',
            'fat': '0',
            'carbs': '0',
            'protein': '0',
            'date': '2025-10-28'
        }

        response = self.client.post(
            reverse('nutrition:log_nutrition'),
            data=data
        )

        self.assertEqual(response.status_code, 200)
        result = json.loads(response.content)
        self.assertTrue(result['success'])
        self.assertEqual(result['calories'], 0.0)


class NutritionModelTestCase(TestCase):
    """Tests for Nutrition model"""

    def test_create_nutrition_entry(self):
        """Test creating a nutrition entry"""
        now = timezone.now()
        entry = NutritionEntry.objects.create(
            source='Manual',
            source_id='test-123',
            consumption_date=now,
            calories=500,
            fat=20,
            carbs=50,
            protein=30
        )

        self.assertEqual(entry.source, 'Manual')
        self.assertEqual(float(entry.calories), 500.0)
        self.assertEqual(float(entry.fat), 20.0)
        self.assertEqual(float(entry.carbs), 50.0)
        self.assertEqual(float(entry.protein), 30.0)

    def test_unique_source_constraint(self):
        """Test that duplicate source entries are prevented"""
        now = timezone.now()
        NutritionEntry.objects.create(
            source='Manual',
            source_id='test-123',
            consumption_date=now,
            calories=500,
            fat=20,
            carbs=50,
            protein=30
        )

        # Should raise error for duplicate source + source_id
        with self.assertRaises(Exception):
            NutritionEntry.objects.create(
                source='Manual',
                source_id='test-123',
                consumption_date=now,
                calories=600,
                fat=25,
                carbs=55,
                protein=35
            )
