import copy
from datetime import date, timedelta
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('profile_art', ROOT/'scripts/generate_profile.py')
art = importlib.util.module_from_spec(spec)
spec.loader.exec_module(art)


def fixture(counts, start=date(2026, 1, 1)):
    days = [dict(date=str(start+timedelta(days=i)), contributionCount=count,
                 contributionLevel='FIRST_QUARTILE' if count else 'NONE',
                 weekday=((start+timedelta(days=i)).weekday()+1)%7) for i,count in enumerate(counts)]
    weeks = []
    for day in days:
        if not weeks or day['weekday']==0:
            weeks.append({'contributionDays': []})
        weeks[-1]['contributionDays'].append(day)
    return dict(login=art.LOGIN,as_of=days[-1]['date'],stars=12,followers=5,repositories=3,
                calendar=dict(totalContributions=sum(counts),weeks=weeks))


class ProfileTests(unittest.TestCase):
    def test_current_streak_today_and_yesterday(self):
        for counts, expected in [([1,2,0,1,3],(2,2)),([1,1,1,0],(3,3)),([1,0,0],(0,1)),([0,0],(0,0))]:
            with self.subTest(counts=counts):
                data=fixture(counts)
                self.assertEqual(art.streaks(art.days_of(data),date.fromisoformat(data['as_of'])),expected)

    def test_year_boundary_and_leap_day(self):
        for start in [date(2025,12,30),date(2024,2,28)]:
            data=fixture([1,1,1,1],start)
            self.assertEqual(art.streaks(art.days_of(data),date.fromisoformat(data['as_of'])),(4,4))

    def test_invalid_data_preserves_existing_assets(self):
        data=fixture([1,2,3])
        for mutate in [lambda d:d.update(login='someone-else'),
                       lambda d:d['calendar'].update(totalContributions=999),
                       lambda d:d.update(as_of='2027-01-01'),
                       lambda d:d['calendar']['weeks'][0]['contributionDays'].pop(1)]:
            broken=copy.deepcopy(data)
            mutate(broken)
            with tempfile.TemporaryDirectory() as directory:
                target=Path(directory)/'contributions.svg'
                target.write_text('last good artwork')
                with self.assertRaises(ValueError):
                    art.render(broken,Path(directory))
                self.assertEqual(target.read_text(),'last good artwork')

    def test_full_year_svg_cells_and_static_fallback(self):
        data=fixture([i%5 for i in range(365)])
        with tempfile.TemporaryDirectory() as directory:
            art.render(data,Path(directory))
            paths=list(Path(directory).glob('*.svg'))
            self.assertEqual(len(paths),3)
            for path in paths:
                root=ET.parse(path).getroot()
                self.assertIn('viewBox',root.attrib)
                content=path.read_text()
                self.assertIn('prefers-reduced-motion',content)
                self.assertNotIn('<script',content)
                self.assertNotIn('http://',content.replace('http://www.w3.org/2000/svg',''))
            root=ET.parse(Path(directory)/'contributions.svg').getroot()
            cells=[e for e in root.iter() if e.attrib.get('class')=='cell']
            self.assertEqual(len(cells),365)
            for cell in cells:
                self.assertLess(float(cell.attrib['x'])+float(cell.attrib['width']),840)
            first={p.name:p.read_bytes() for p in paths}
            art.render(data,Path(directory))
            self.assertEqual(first,{p.name:p.read_bytes() for p in paths})

    def test_xml_escaping(self):
        ET.fromstring(art.svg(410,426,'A & B < C',art.text(1,2,'<test> & value')))

    @patch.dict('os.environ', {'GH_TOKEN':'test-only'})
    @patch.object(art.urllib.request,'urlopen')
    def test_pagination(self, request):
        data=fixture([1,2])
        def response(stars,more):
            user=dict(login=art.LOGIN,followers={'totalCount':5},
                      repositories=dict(totalCount=2,nodes=[{'stargazerCount':stars}],pageInfo=dict(hasNextPage=more,endCursor='next')),
                      contributionsCollection={'contributionCalendar':data['calendar']})
            from io import BytesIO
            return BytesIO(json.dumps({'data':{'user':user}}).encode())
        request.side_effect=[response(4,True),response(8,False)]
        result=art.fetch(date(2026,1,2))
        self.assertEqual(result['stars'],12)
        second=json.loads(request.call_args_list[1].args[0].data)
        self.assertEqual(second['variables']['cursor'],'next')

    @patch.dict('os.environ', {'GH_TOKEN':'test-only'})
    @patch.object(art.urllib.request,'urlopen')
    def test_api_errors_fail(self,request):
        from io import BytesIO
        request.return_value=BytesIO(b'{"errors":[{"message":"rate limited"}]}')
        with self.assertRaises(ValueError):
            art.fetch(date(2026,1,2))


if __name__=='__main__':
    unittest.main()
