import copy
import json
from pathlib import Path
import sys
import unittest
import xml.etree.ElementTree as ET
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
import generate_profile as profile


def days(counts):
    return [{'contributionCount': value} for value in counts]


class ProfileTests(unittest.TestCase):
    def test_streak_boundaries(self):
        for counts, expected in [([0, 0], (0, 0)), ([1, 1, 0], (2, 2)),
                                 ([1, 0, 0], (0, 1)), ([1, 1, 0, 1], (1, 2)),
                                 ([1]*365, (365, 365))]:
            with self.subTest(counts=counts):
                self.assertEqual(profile.streaks(days(counts)), expected)

    def test_snapshot_and_svg_integrity(self):
        data = json.loads((profile.ROOT/'assets/profile-data.json').read_text())
        profile.validate(data)
        art = [profile.heatmap(data), profile.terminal(), *profile.cards(data)]
        for svg in art:
            root = ET.fromstring(svg)
            self.assertTrue(root.attrib['viewBox'])
            self.assertIn('prefers-reduced-motion', svg)
            self.assertNotIn('<script', svg)
            self.assertNotIn('AVIVASHISHTA29', svg)
        root = ET.fromstring(art[0])
        cells = [e for e in root.iter() if e.attrib.get('class') == 'cell']
        self.assertEqual(len(cells), 365)
        self.assertTrue(all(float(c.attrib['x'])+11 < 860 for c in cells))
        self.assertEqual(sum(d['contributionCount'] for d in data['days']),
                         sum(int(c[0].text.split(': ')[1].split()[0]) for c in cells))

    def test_incomplete_data_is_rejected(self):
        data = json.loads((profile.ROOT/'assets/profile-data.json').read_text())
        bad = copy.deepcopy(data)
        bad['days'].pop(3)
        with self.assertRaises(ValueError):
            profile.validate(bad)
        bad = copy.deepcopy(data)
        bad['login'] = 'someone-else'
        with self.assertRaises(ValueError):
            profile.validate(bad)

    def test_public_repository_pagination(self):
        def response(stars, more):
            return {'followers': {'totalCount': 4}, 'repositories': {
                'totalCount': 101, 'nodes': [{'stargazerCount': stars}],
                'pageInfo': {'hasNextPage': more, 'endCursor': 'next'}},
                'contributionsCollection': {'contributionCalendar': {'weeks': []}}}
        with patch.object(profile, 'graphql', side_effect=[response(12, True), response(8, False)]) as query:
            result = profile.fetch(profile.date(2026, 10, 9))
        self.assertEqual(result['stars'], 20)
        self.assertEqual(result['repositories'], 101)
        self.assertEqual(query.call_count, 2)

    def test_xml_escaping(self):
        self.assertIn('&lt;tag&gt; &amp;', profile.text(0, 0, '<tag> &'))


if __name__ == '__main__':
    unittest.main()
