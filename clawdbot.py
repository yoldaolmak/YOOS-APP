import argparse
import sys
import os
from dotenv import load_dotenv

load_dotenv()


def run_command(args):
    import sys
    import os
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

    from wp import get_post, save_as_draft, set_active_site
    from multi_ai import reset_session_cost, print_session_cost
    reset_session_cost()

    # Aktif siteyi ayarla (yoldaolmak veya gezievreni)
    set_active_site(args.site)

    mode = args.mode or 'guide'

    print("\n" + "=" * 65)
    print("🤖 CLAWDBOT v8.4  |  RUN MODE")
    print("=" * 65)
    print(f"📍 Site  : {args.site}")
    print(f"🆔 Post  : {args.post}")
    print(f"🎯 Mod   : {mode.upper()}")
    print("=" * 65)

    print(f"\n📥 WordPress'ten post çekiliyor (ID: {args.post})...")
    post = get_post(args.post)
    if not post:
        print(f"❌ Post {args.post} bulunamadı.")
        return

    raw_title = post.get("title", {})
    title = raw_title.get("rendered", "") if isinstance(raw_title, dict) else str(raw_title)
    raw_content = post.get("content", {})
    content_html = raw_content.get("rendered", "") if isinstance(raw_content, dict) else str(raw_content)

    print(f"✅ Post çekildi: {title}")
    print(f"📝 Orijinal içerik: {len(content_html):,} karakter")

    if args.schema:
        print("⚠️  Schema standalone modu bu sürümde henüz aktif değil.")
        return

    yoast_meta = None  # where mode doldurur

    if mode == 'guide':
        from guide_engine import generate_guide
        print("\n📖 GUIDE ENGINE başlatılıyor...")
        new_title, new_content = generate_guide(post)

    elif mode == 'schema':
        from schema_engine import run_schema_mode
        print("\n🟣 SCHEMA ENGINE başlatılıyor...")
        new_title, new_content = run_schema_mode(post)

    elif mode == 'where':
        from where_engine import generate_where
        print("\n🗺️  WHERE ENGINE başlatılıyor...")
        new_title, new_content, yoast_meta = generate_where(post)
        print(f"\n📋 Yoast SEO:")
        print(f"   Title   : {yoast_meta['title']}")
        print(f"   Desc    : {yoast_meta['desc'][:80]}...")
        print(f"   Focus KW: {yoast_meta['focuskw']}")

    elif mode in ('travel',):
        print(f"⚠️  {mode.upper()} modu icin guide_engine kullaniliyor (fallback)...")
        from guide_engine import generate_guide
        new_title, new_content = generate_guide(post)

    elif mode == 'polish':
        from polish_engine import run_polish
        dry_run = getattr(args, 'dry_run', False)
        print(f"\n✨ POLISH ENGINE başlatılıyor{' (DRY-RUN)' if dry_run else ''}...")
        result = run_polish(post, dry_run=dry_run)
        print_session_cost()
        return

    elif mode == 'audit':
        # run --mode audit → audit komutuna yönlendir, draft oluşturma
        print("\n⚖️  AUDIT modu — draft oluşturulmayacak, sadece skor.")
        print("   Ipucu: Daha detaylı rapor için: clawdbot.py audit --post " + str(args.post))
        from audit_engine import run_audit, print_audit_report, save_report
        report = run_audit(post_id=args.post)
        print_audit_report(report)
        save_report(report, './reports')
        print_session_cost()
        return

    else:
        print(f"❌ Bilinmeyen mod: {mode}")
        return

    # Guide/where/schema mode → ASLA mevcut postu ezme.
    # Yeni draft post açılır; orijinal post dokunulmaz.
    cats = post.get("categories", [])
    tags = post.get("tags", [])

    print(f"\n💾 Yeni DRAFT post oluşturuluyor...")
    new_post_id = save_as_draft(
        title=new_title,
        content=new_content,
        categories=cats,
        tags=tags,
        yoast_meta=yoast_meta,
    )

    print("\n" + "=" * 65)
    if new_post_id:
        print(f"✅ YENİ DRAFT OLUŞTURULDU")
        print(f"   Yeni Draft ID : {new_post_id}")
        print(f"   Kaynak Post   : {args.post}  (orijinal — dokunulmadı)")
        print(f"   Başlık        : {new_title}")
        wp_url = os.environ.get("WP_URL", "https://yoldaolmak.com")
        print(f"   Önizleme      : {wp_url}/?p={new_post_id}&preview=true")
        print(f"   Düzenle       : {wp_url}/wp-admin/post.php?post={new_post_id}&action=edit")
    else:
        print("❌ Draft oluşturulamadı. WP credentials ve bağlantıyı kontrol edin.")
    print("=" * 65)
    print_session_cost()


def audit_command(args):
    import sys
    import os
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

    from audit_engine import run_audit, print_audit_report, save_report

    content_type = getattr(args, 'type', 'Destination_Guide') or 'Destination_Guide'

    print("\n" + "=" * 65)
    print("⚖️  CLAWDBOT v8.3  |  AUDIT MODE")
    print("=" * 65)

    if hasattr(args, 'batch') and args.batch:
        # Batch mod: dosyadan URL listesi oku
        batch_file = args.batch
        if not os.path.exists(batch_file):
            print(f"❌ Batch dosyası bulunamadı: {batch_file}")
            return

        with open(batch_file, encoding='utf-8') as f:
            urls = [line.strip() for line in f if line.strip() and not line.startswith('#')]

        print(f"📋 Batch audit: {len(urls)} URL")
        print(f"📂 Raporlar: {args.report_dir}\n")

        results = []
        for i, url in enumerate(urls, 1):
            print(f"\n[{i}/{len(urls)}] {url}")
            try:
                report = run_audit(url=url, content_type=content_type)
                print_audit_report(report)
                filepath = save_report(report, args.report_dir)
                print(f"💾 Kaydedildi: {filepath}")
                results.append({
                    "url": url,
                    "total_score": report.get("scores", {}).get("total", 0),
                    "verdict": report.get("verdict", "-"),
                    "publish_ready": report.get("publish_ready", False),
                    "report_file": filepath,
                })
            except Exception as e:
                print(f"❌ Hata: {e}")
                results.append({"url": url, "error": str(e)})

        # Batch özet
        import json
        print("\n" + "=" * 65)
        print("📊 BATCH AUDİT ÖZETİ")
        print("=" * 65)
        ready = [r for r in results if r.get("publish_ready")]
        needs_revision = [r for r in results if not r.get("publish_ready") and not r.get("error")]
        errors = [r for r in results if r.get("error")]
        print(f"  ✅ Yayına hazır    : {len(ready)}")
        print(f"  🔧 Revizyon gerekli: {len(needs_revision)}")
        print(f"  ❌ Hata            : {len(errors)}")

        # Sıralanmış sonuçlar
        scored = sorted([r for r in results if "total_score" in r],
                        key=lambda x: x["total_score"], reverse=True)
        print("\n  Skor sıralaması:")
        for r in scored[:10]:
            score = r.get("total_score", 0)
            verdict = r.get("verdict", "-")[:25]
            url_short = r.get("url", "")[-50:]
            print(f"  {score:>5.1f} | {verdict:<25} | ...{url_short}")

        # Batch raporu kaydet
        import datetime
        ts = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        batch_report_path = os.path.join(args.report_dir, f"batch_summary_{ts}.json")
        os.makedirs(args.report_dir, exist_ok=True)
        with open(batch_report_path, 'w', encoding='utf-8') as f:
            json.dump(results, f, ensure_ascii=False, indent=2)
        print(f"\n💾 Batch özet kaydedildi: {batch_report_path}")

    else:
        # Tek URL modu
        url = getattr(args, 'url', None)
        post_id = getattr(args, 'post', None)

        if post_id:
            # Post ID'den URL üret
            wp_url = os.environ.get("WP_URL", "https://yoldaolmak.com")
            url = f"{wp_url}/?p={post_id}"
            print(f"📍 Post ID {post_id} → {url}")
        elif not url:
            print("❌ --url veya --post gerekli")
            return

        report = run_audit(url=url, content_type=content_type)
        print_audit_report(report)
        filepath = save_report(report, args.report_dir)
        print(f"💾 Rapor kaydedildi: {filepath}\n")


def daily_command(args):
    """GSC → önceliklendirme → günlük N post işleme."""
    import sys, os
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

    from gsc_client import fetch_historical_comparison, load_gsc_cache, save_gsc_cache
    from priority_engine import build_queue, get_next_batch, mark_processed, queue_status
    from audit_engine import run_audit, save_report
    from editorial_mode import run_editorial_rewrite
    from memory import (record_audit, record_action, record_gsc_snapshot,
                        update_recommendation, should_skip, print_memory_report)

    limit = args.limit or 10
    mode = args.mode or 'auto'
    report_dir = args.report_dir or './reports'

    print("\n" + "=" * 65)
    print("🤖 CLAWDBOT v8.3  |  DAILY MODE")
    print("=" * 65)
    print(f"📋 Günlük hedef  : {limit} post")
    print(f"🎯 İşlem modu    : {mode.upper()}")
    print("=" * 65)

    # 1. GSC verisi — cache varsa kullan
    print("\n📡 ADIM 1/4: GSC Verisi")
    gsc_data = load_gsc_cache()
    if gsc_data is None:
        print("   API'den taze veri çekiliyor...")
        try:
            gsc_data = fetch_historical_comparison(months_recent=3)
            save_gsc_cache(gsc_data)
        except Exception as e:
            print(f"   ❌ GSC hatası: {e}")
            print("   ℹ️  GSC olmadan devam etmek için --batch ile URL listesi kullan.")
            return

    # 2. Kuyruk güncelle
    print("\n📊 ADIM 2/4: Önceliklendirme")
    queue = build_queue(gsc_data, max_results=50)

    # 3. Sonraki batch
    batch = get_next_batch(limit)
    if not batch:
        print("\n✅ Kuyrukta işlenecek URL kalmadı.")
        print("   GSC cache temizle ve kuyruğu yenile: --refresh-queue")
        return

    print(f"\n⚙️  ADIM 3/4: {len(batch)} Post İşleniyor")
    print("-" * 65)

    results = []
    for i, item in enumerate(batch, 1):
        url = item["url"]
        content_type = item.get("content_type", "Destination_Guide")
        group = item.get("group", "B")
        priority = item.get("priority_score", 0)

        print(f"\n[{i}/{len(batch)}] Grup:{group} Skor:{priority} | {url}")

        # Hafıza: skip kontrolü
        skip, skip_reason = should_skip(url)
        if skip:
            print(f"   ⏸️  ATLA: {skip_reason}")
            results.append({"url": url, "action": "SKIPPED", "reason": skip_reason})
            continue

        # Önce audit et — karar ver
        print("   ⚖️  Audit çalışıyor...")
        try:
            audit_report = run_audit(url=url, content_type=content_type)
            audit_score = audit_report.get("scores", {}).get("total", 0)
            verdict = audit_report.get("verdict", "")
            save_report(audit_report, report_dir)
            print(f"   Audit skoru: {audit_score}/100 → {verdict}")
            # Hafıza: skoru kaydet
            record_audit(url, audit_score, content_type=content_type, group=group)
        except Exception as e:
            print(f"   ❌ Audit hatası: {e}")
            audit_score = 0
            verdict = "HATA"

        # Moda göre işlem kararı
        action_taken = "ATLA"

        if mode == 'audit_only':
            # Sadece audit — düzeltme yok
            action_taken = "AUDIT_ONLY"

        elif mode == 'auto' or mode == 'rewrite':
            # Skor eşiğine göre otomatik karar
            if audit_score >= 82:
                print(f"   ✅ Skor {audit_score} >= 82, müdahale gerekmiyor.")
                action_taken = "SKIP_GOOD"
            elif audit_score >= 55:
                print(f"   🔧 Skor {audit_score}: editorial_rewrite uygulanıyor...")
                try:
                    result = run_editorial_rewrite(
                        url=url,
                        max_passes=2,
                        backup_dir='./backups',
                        report_dir=report_dir
                    )
                    if result.get('success'):
                        draft_id = result.get('draft_id', '-')
                        draft_title = result.get('draft_title', '-')
                        print(f"   ✅ Draft kaydedildi: ID={draft_id} | '{draft_title}'")
                        action_taken = "REWRITE"
                        record_action(url, "editorial_rewrite",
                                      score_before=audit_score,
                                      draft_id=draft_id if isinstance(draft_id, int) else None,
                                      draft_title=draft_title)
                    else:
                        print(f"   ❌ Rewrite başarısız.")
                        action_taken = "REWRITE_FAIL"
                except Exception as e:
                    print(f"   ❌ Rewrite hatası: {e}")
                    action_taken = "REWRITE_FAIL"
            else:
                print(f"   ⚠️  Skor {audit_score} < 55: run --mode guide ile tam yeniden yazım öneriliyor.")
                print(f"   ℹ️  Bu URL'yi run listesine taşı: clawdbot.py run yoldaolmak --post <ID>")
                action_taken = "NEEDS_FULL_REWRITE"

        mark_processed(url, audit_score)
        # Hafıza: öneriyi güncelle
        rec_data = update_recommendation(url)
        print(f"   🧠 Sonraki öneri: {rec_data['action']} — {rec_data['reason'][:60]}")
        results.append({
            "url": url,
            "audit_score": audit_score,
            "verdict": verdict,
            "action": action_taken,
            "group": group
        })
        print(f"   ✓ İşaretlendi: processed=True")

    # 4. Özet
    print("\n" + "=" * 65)
    print("📊 ADIM 4/4: Günlük Özet")
    print("=" * 65)

    status = queue_status()
    print(f"  İşlenen bugün     : {len(results)}")
    print(f"  Kuyrukta kalan    : {status['pending']}")
    print(f"  Toplam işlenen    : {status['processed']}/{status['total']}")
    print(f"  Ort. audit skoru  : {status['avg_audit_score'] or '-'}")

    print("\n  Bugünkü sonuçlar:")
    for r in results:
        score = r.get('audit_score', '-')
        action = r.get('action', '-')
        url_short = r['url'].split('/')[-1][:40]
        print(f"  {score:>5} | {action:<22} | {url_short}")

    print()


def status_command(args):
    """Kuyruk durumu ve sistem sağlığı."""
    import sys, os
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

    from priority_engine import queue_status, export_batch_txt, load_queue
    from gsc_client import load_gsc_cache
    from memory import memory_summary

    print("\n" + "=" * 65)
    print("📊 CLAWDBOT STATUS")
    print("=" * 65)

    # Kuyruk
    status = queue_status()
    print(f"\n  KUYRUK:")
    print(f"  Toplam URL       : {status['total']}")
    print(f"  İşlendi          : {status['processed']}")
    print(f"  Bekliyor         : {status['pending']}")
    print(f"  Grup A bekliyor  : {status['group_pending'].get('A', 0)}")
    print(f"  Grup B bekliyor  : {status['group_pending'].get('B', 0)}")
    print(f"  Grup C bekliyor  : {status['group_pending'].get('C', 0)}")
    print(f"  Ort. audit skoru : {status['avg_audit_score'] or 'henüz yok'}")

    # GSC cache
    cache = load_gsc_cache(max_age_hours=999)
    if cache:
        print(f"\n  GSC CACHE: {len(cache)} URL kayıtlı")
    else:
        print(f"\n  GSC CACHE: boş — ilk daily çalışmasında doldurulacak")

    # Tahmin
    if status['pending'] > 0:
        days = (status['pending'] + 9) // 10
        print(f"\n  Günde 10 post ile {days} gün içinde kuyruk tamamlanır")

    # Export seçeneği
    if args.export:
        path = export_batch_txt(args.export)
        print(f"\n  ✅ Kuyruk dışa aktarıldı: {path}")

    # Hafıza özeti
    msummary = memory_summary()
    if msummary.get("total_urls", 0) > 0:
        print(f"\n  HAFIZA:")
        print(f"  Takip edilen URL    : {msummary['total_urls']}")
        print(f"  Ort. audit skoru    : {msummary.get('avg_audit_score', '-')}")
        print(f"  Yayına hazır (82+)  : {msummary.get('publish_ready', 0)}")
        print(f"  Tam yeniden yazım   : {msummary.get('needs_full_rewrite', 0)}")
        trends = msummary.get("score_trends", {})
        print(f"  Trend (iyi/kötü/düz): {trends.get('improving',0)}/{trends.get('declining',0)}/{trends.get('flat',0)}")
        stubborn = msummary.get("stubborn_urls", [])
        if stubborn:
            print(f"\n  INATÇI URLLAR (3+ deneme, skor < 70):")
            for s in stubborn:
                url_s = s['url'].split('/')[-1][:40]
                print(f"    {s['attempts']} deneme | skor:{s['last_score']} | {url_s}")

    # Son işlenenler
    queue = load_queue()
    processed = [x for x in queue if x.get("processed") and x.get("last_processed_at")]
    processed.sort(key=lambda x: x.get("last_processed_at", ""), reverse=True)
    if processed:
        print(f"\n  SON İŞLENENLER:")
        for item in processed[:5]:
            score = item.get("last_audit_score", "-")
            dt = item.get("last_processed_at", "")[:10]
            url_short = item["url"].split("/")[-1][:40]
            print(f"  {dt} | skor:{score} | {url_short}")

    print()


def editorial_rewrite_command(args):
    from editorial_mode import run_editorial_rewrite
    
    if not args.url:
        print("Error: --url is required for editorial_rewrite mode")
        sys.exit(1)
    
    result = run_editorial_rewrite(
        url=args.url,
        max_passes=args.max_passes or 2,
        output_dir=args.output_dir or "./output",
        backup_dir=args.backup_dir or "./backups",
        report_dir=args.report_dir or "./reports"
    )
    
    if result['success']:
        sys.exit(0)
    else:
        print(f"\n❌ Editorial rewrite failed: {result.get('error', 'Unknown error')}")
        sys.exit(1)


def main():
    parser = argparse.ArgumentParser(description='Yoldaolmak.com Content Engine')
    subparsers = parser.add_subparsers(dest='subcommand', help='Subcommands')
    
    run_parser = subparsers.add_parser('run', help='Run content generation')
    run_parser.add_argument('site', help='Site name')
    run_parser.add_argument('--post', type=int, required=True, help='Post ID')
    run_parser.add_argument('--mode', choices=['travel', 'where', 'guide', 'schema', 'audit', 'polish'],
                            help='Generation mode (audit: sadece skor | polish: cerrahi iyilestirme)')
    run_parser.add_argument('--dry-run', action='store_true',
                            help="Polish: WP'ye yazma, sadece diff raporu goster")
    run_parser.add_argument('--schema', nargs='?', const='auto', choices=['auto', 'where', 'guide'], help='Add schema/FAQ only')
    
    audit_parser = subparsers.add_parser('audit', help='Editorial audit council — 3 yargicli degerlendirme')
    audit_group = audit_parser.add_mutually_exclusive_group()
    audit_group.add_argument('--url', help='Audit edilecek makale URL-i')
    audit_group.add_argument('--post', type=int, help='WordPress post ID')
    audit_group.add_argument('--batch', help='URL listesi dosyasi (her satir bir URL)')
    audit_parser.add_argument('--type', default='Destination_Guide',
                              choices=['Destination_Guide', 'Things_To_Do', 'Places_To_Visit'],
                              help='Icerik tipi')
    audit_parser.add_argument('--report-dir', default='./reports', help='Rapor klasoru')

    daily_parser = subparsers.add_parser('daily', help='GSC verisinden gunluk N post isle')
    daily_parser.add_argument('--limit', type=int, default=10, help='Gunluk post limiti (varsayilan: 10)')
    daily_parser.add_argument('--mode', default='auto',
                              choices=['auto', 'audit_only', 'rewrite'],
                              help='auto=akilli karar | audit_only=sadece skor | rewrite=her zaman yaz')
    daily_parser.add_argument('--refresh-queue', action='store_true', help='Cache temizle, kuyruğu yenile')
    daily_parser.add_argument('--report-dir', default='./reports', help='Rapor klasoru')

    status_parser = subparsers.add_parser('status', help='Kuyruk durumu ve sistem ozeti')
    status_parser.add_argument('--export', default=None, metavar='FILE',
                               help='Kuyrugu txt dosyasina aktar (orn: top50.txt)')

    editorial_parser = subparsers.add_parser('editorial_rewrite', help='Editorial surgical rewrite')
    editorial_parser.add_argument('--url', required=True, help='WordPress post URL')
    editorial_parser.add_argument('--max-passes', type=int, default=2, choices=[1, 2], help='Max passes')
    editorial_parser.add_argument('--output-dir', default='./output', help='Output directory')
    editorial_parser.add_argument('--backup-dir', default='./backups', help='Backup directory')
    editorial_parser.add_argument('--report-dir', default='./reports', help='Report directory')
    
    args = parser.parse_args()
    
    if not args.subcommand:
        parser.print_help()
        sys.exit(1)
    
    if args.subcommand == 'run':
        run_command(args)
    elif args.subcommand == 'audit':
        audit_command(args)
    elif args.subcommand == 'daily':
        daily_command(args)
    elif args.subcommand == 'status':
        status_command(args)
    elif args.subcommand == 'editorial_rewrite':
        editorial_rewrite_command(args)
    else:
        parser.print_help()
        sys.exit(1)


if __name__ == "__main__":
    main()