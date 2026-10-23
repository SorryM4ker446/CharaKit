"""Browser regressions for real helper HTML and the portable QA viewer (synthetic inputs)."""
import argparse
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
import json
from pathlib import Path
import threading


def verify(inputs, output):
    from playwright.sync_api import sync_playwright
    inputs, output = Path(inputs).resolve(), Path(output).resolve()
    output.mkdir(parents=True, exist_ok=False)
    fixtures = json.loads(inputs.read_text(encoding='utf-8'))
    served = inputs.parent
    checks, errors = [], []

    def check(name, passed, **evidence):
        checks.append(dict(name=name, passed=bool(passed), **evidence))

    class QuietHandler(SimpleHTTPRequestHandler):
        def log_message(self, *args):
            pass

    server = ThreadingHTTPServer(('127.0.0.1', 0), partial(QuietHandler, directory=str(served)))
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    origin = 'http://127.0.0.1:' + str(server.server_port)

    def url(path):
        from urllib.parse import quote
        return origin + '/' + quote(Path(path).resolve().relative_to(served).as_posix())

    try:
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch()
            page = browser.new_page(viewport=dict(width=1440, height=1000))
            page.on('pageerror', lambda error: errors.append(str(error)))
            page.on('requestfailed', lambda request: errors.append(request.url + ': ' + str(request.failure)))
            page.goto(url(fixtures['review']))
            page.wait_for_function("Array.from(document.querySelectorAll('.grid img')).every(x=>x.complete&&x.naturalWidth>0)")
            check('review_has_source_and_two_versions', page.locator('.grid').first.locator('img').count() == 3)
            check('review_no_implicit_choice', page.locator('#candidate').input_value() == '' and page.locator('#decision').input_value() == '')
            check('review_resolution_warning', page.locator('.canvas-warning').is_visible() and '允许导出' in page.locator('.canvas-warning').inner_text())
            page.locator('#download').click()
            check('empty_feedback_blocked', bool(page.locator('#message').inner_text()))
            page.locator('[data-review-candidate="A"][data-decision="accept"]').first.click()
            page.locator('[data-viewer-index="1"][data-view="full"]').click()
            page.locator('#compare-source').check()
            page.locator('#zoom').fill('250')
            page.locator('#zoom').dispatch_event('input')
            page.wait_for_function("!document.querySelector('#viewer-status').textContent.includes('加载中')")
            page.locator('#viewport').evaluate("x=>{x.scrollTop=120;x.dispatchEvent(new Event('scroll'));}")
            page.wait_for_function("document.querySelector('#source-viewport').scrollTop>0")
            positions = page.locator('#viewport,#source-viewport').evaluate_all("xs=>xs.map(x=>(x.scrollTop+x.clientHeight/2)/x.firstElementChild.clientHeight)")
            check('source_comparison_position_synced', abs(positions[0] - positions[1]) < .01)
            page.locator('#next').click()
            page.wait_for_function("!document.querySelector('#viewer-status').textContent.includes('加载中')")
            check('browse_keeps_choice_and_zoom', page.locator('#candidate').input_value() == 'A' and page.locator('#zoom').input_value() == '250')
            page.locator('#inspection-area').select_option('face')
            page.wait_for_function("document.querySelector('#viewer-image').complete&&document.querySelector('#viewer-image').naturalWidth>0")
            check('face_detail_loaded', 'face-' in page.locator('#viewer-image').get_attribute('src'))
            page.keyboard.press('Escape')
            page.locator('#decision').select_option('revise')
            page.locator('#note').fill('[QA FIXTURE] Synthetic feedback download only; not submitted.')
            with page.expect_download() as pending:
                page.locator('#download').click()
            target = output / 'feedback.fixture.json'
            pending.value.save_as(target)
            feedback = json.loads(target.read_text(encoding='utf-8'))
            check('downloaded_feedback_exact', feedback['candidate'] == 'A' and feedback['decision'] == 'revise' and feedback['note'].startswith('[QA FIXTURE]'))
            page.evaluate("Object.defineProperty(navigator.clipboard,'writeText',{configurable:true,value:async()=>{throw Error('QA denied')}})")
            page.locator('#copy-feedback').click()
            page.wait_for_function("document.querySelector('#message').textContent.includes('无法自动复制')")
            check('clipboard_denied_has_complete_fallback', json.loads(page.locator('#copy-output').input_value()) == feedback)
            page.reload()
            check('reload_does_not_accept_draft', page.locator('#candidate').input_value() == '' and page.locator('#decision').input_value() == '')
            page.set_viewport_size(dict(width=390, height=844))
            check('mobile_review_warning_and_no_overflow', page.locator('.canvas-warning').is_visible() and page.evaluate('document.documentElement.scrollWidth<=innerWidth'))
            page.screenshot(path=str(output / 'review-mobile.png'), full_page=True)

            page.goto(url(fixtures['inspection']))
            page.wait_for_function('qa.preloads.every(x=>x.complete&&x.naturalWidth>0)')
            check('inspection_all_images_loaded', page.evaluate('qa.assets.length===3 && qa.errors.length===0'))
            page.set_viewport_size(dict(width=1440, height=1000))
            for height in ('420', '720'):
                page.locator('#height').select_option(height)
                for asset in page.evaluate('qa.assets.map(x=>x.id)'):
                    page.locator('#second').select_option(asset)
                    page.wait_for_function("document.querySelector('#image-b').complete && document.querySelector('#image-b').naturalWidth>0")
                    bounds = page.locator('#image-b').evaluate("x=>({height:x.getBoundingClientRect().height,bottom:x.getBoundingClientRect().bottom-x.closest('.stage').getBoundingClientRect().bottom})")
                    check(f'height_{height}_{asset}_bottom_anchor', abs(bounds['height'] - int(height)) < 1 and abs(bounds['bottom']) <= 2)
            page.locator('#first').select_option('0:source')
            page.locator('#second').select_option('0:happy_v001')
            page.locator('#mode').select_option('scale')
            heights = page.locator('#image-a,#image-b').evaluate_all('xs=>xs.map(x=>x.getBoundingClientRect().height)')
            check('same_pixel_scale_exposes_size_difference', abs(heights[1] / heights[0] - .5) < .001)
            page.locator('#mode').select_option('native')
            check('native_pixels_not_rescaled', page.locator('#image-b').evaluate('x=>x.getBoundingClientRect().height===x.naturalHeight'))
            page.locator('#mode').select_option('height')
            page.locator('#first').select_option('0:happy_v001')
            page.locator('#second').select_option('0:happy_v002')
            check('mixed_dimensions_visible', '80 × 160' in page.locator('#warning').inner_text() and '80 × 161' in page.locator('#warning').inner_text())
            page.locator('#background').select_option('dark')
            check('dark_background', page.locator('body').get_attribute('class') == 'dark')
            before = page.evaluate('qa.changes')
            page.locator('#play').click()
            page.wait_for_function('before=>qa.changes>=before+3', arg=before)
            page.keyboard.press('Escape')
            stopped = page.evaluate('qa.changes')
            page.wait_for_timeout(700)
            check('loop_switches_and_esc_stops', stopped >= before + 3 and page.evaluate('qa.changes') == stopped)
            page.screenshot(path=str(output / 'switching-desktop.png'), full_page=True)
            page.set_viewport_size(dict(width=390, height=844))
            check('mobile_inspection_no_overflow', page.evaluate('document.documentElement.scrollWidth<=innerWidth'))
            check('no_script_or_resource_errors', not errors, errors=errors)
            browser.close()
    except Exception as exc:
        check('browser_error', False, detail=str(exc))
    finally:
        server.shutdown()
        server.server_close()
        thread.join()
    result = dict(passed=bool(checks) and all(c['passed'] for c in checks), checks=checks,
                  visual_quality='not_assessed', fixture_only=True)
    (output / 'results.json').write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding='utf-8')
    return result


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--inputs', required=True, type=Path)
    parser.add_argument('--output', required=True, type=Path)
    args = parser.parse_args()
    result = verify(args.inputs, args.output)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    raise SystemExit(0 if result['passed'] else 1)
