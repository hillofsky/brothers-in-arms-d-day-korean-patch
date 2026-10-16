# 작업 이력 탐색

기록일: 2026-10-16. 아래 단계명은 파일명에서 추출한 **탐색용 분류**이며 실행 순서나 최신 성공 빌드를 뜻하지 않는다. 원문 보고서의 상태는 당시 결과다. 현재 기준은 PROJECT_STATE.md와 배포 manifest다.

대조 후보 2,214건: SANITIZED_ARCHIVE 1,577, DUPLICATE_ARCHIVED 634, WITHHELD_SIZE_LIMIT 3.

[전체 대조 목록](HISTORY_INVENTORY.json), [함수·import 탐색](SOURCE_MAP.json), [확인된 지식과 실패 기록](KNOWLEDGE_LEDGER.md)을 함께 읽는다.

공개된 history/는 개인 경로를 치환하고 큰 payload/민감 필드를 제외한 기록용 사본이다. **그대로 실행하거나 과거 인계 지시를 현재 지시로 적용하지 않는다.** 원본 SHA-256과 공개본 해시를 대조 목록에 구분했다.

| 분류 | 후보 수 | 보고서에 적힌 상태 (일부) | 근거 예시 |
|---|---:|---|---|
| OTHER | 413 | 명시 없음/코드만 있음 | [report](../history/evidence/session-work/16126538f65ad5d8_gpu_dump18_summary.json) · [report](../history/evidence/session-work/17370571849cee49_gpu_dump19_summary.json) |
| STAGE1 | 2 | 명시 없음/코드만 있음 | [source](../history/sources/project/31e8e7f50112b1d9_bia_stage01_inventory.py) · [source](../history/sources/project/76518358d2ecd3e9_run_bia_stage01.ps1) |
| STAGE2 | 2 | 명시 없음/코드만 있음 | [source](../history/sources/project/9bb831875e2b684a_bia_stage02_collect.py) · [source](../history/sources/project/1daf952708bd52e6_run_bia_stage02.ps1) |
| STAGE3 | 2 | 명시 없음/코드만 있음 | [source](../history/sources/project/b5ccc6e266c18857_bia_stage03_font_assets.py) · [source](../history/sources/project/444b963f3acbc595_run_bia_stage03.ps1) |
| STAGE4 | 3 | 명시 없음/코드만 있음 | [source](../history/sources/project/fdafbbd50c8ecae0_bia_stage04_mdi_unicode_test.py) · [source](../history/sources/project/2cb62f2cadf92d01_run_bia_stage04.ps1) |
| STAGE4B | 2 | 명시 없음/코드만 있음 | [source](../history/sources/project/119c0722d652f615_bia_stage04b_localize_test.py) · [source](../history/sources/project/b35afc6218df512f_run_bia_stage04b.ps1) |
| STAGE5 | 2 | 명시 없음/코드만 있음 | [source](../history/sources/project/a68f6aa1233bc866_bia_stage05_ram_live_probe.py) · [source](../history/sources/project/73edb4c038e1b105_run_bia_stage05.ps1) |
| STAGE6 | 2 | 명시 없음/코드만 있음 | [source](../history/sources/project/fb95133540f9ad35_bia_stage06_fontmap_probe.py) · [source](../history/sources/project/27a5ad368bcf7e5b_run_bia_stage06.ps1) |
| STAGE6B | 3 | 명시 없음/코드만 있음 | [report](../history/evidence/project/4caae02b94c876c2_stage06b_results.json) · [source](../history/sources/project/21265c3d64aa46e9_bia_stage06b_font_lookup_diag.py) |
| STAGE7 | 3 | 명시 없음/코드만 있음 | [report](../history/evidence/project/ad3faea46cd35d33_stage07_report.json) · [source](../history/sources/project/709d1b1e85b1ebff_bia_stage07_preload_fontmap.py) |
| STAGE8 | 3 | 명시 없음/코드만 있음 | [report](../history/evidence/project/26c0c409a75cb6b8_stage08_report.json) · [source](../history/sources/project/0a0dd2a1748b75de_bia_stage08_direct_charmap_probe.py) |
| STAGE9 | 3 | 명시 없음/코드만 있음 | [report](../history/evidence/project/9dc38e6ed32f310a_summary.json) · [source](../history/sources/project/f70e1a6549c36fcc_bia_stage09_texture_dump.py) |
| STAGE10 | 5 | 명시 없음/코드만 있음 | [report](../history/evidence/project/a1991ac6ced5314f_stage10_report.json) · [source](../history/sources/project/2db3bdd482ada2a7_bia_stage10_real_hangul.py) |
| STAGE11 | 3 | 명시 없음/코드만 있음 | [report](../history/evidence/project/27d8c72fcdea2f99_stage11_report.json) · [source](../history/sources/project/7d0c90b5e0f12a5f_bia_stage11_charmap_boundary.py) |
| STAGE12 | 3 | 명시 없음/코드만 있음 | [report](../history/evidence/project/3ea27fef61f78315_stage12_report.json) · [source](../history/sources/project/eaeb7bf872f3c0db_bia_stage12_unicode_page.py) |
| STAGE13 | 4 | 명시 없음/코드만 있음 | [report](../history/evidence/project/e665ee5f1924ef13_stage13_report.json) · [source](../history/sources/project/11e47d27a5cd25f7_bia_stage13_auto_runner.py) |
| STAGE13B | 3 | 명시 없음/코드만 있음 | [source](../history/sources/project/88e6d8b87ed0bd2d_bia_stage13_auto_runner.py) · [source](../history/sources/project/f9f1fa99190170b4_capture_ppsspp.ps1) |
| STAGE14 | 3 | 명시 없음/코드만 있음 | [source](../history/sources/project/ba3bbfea8d47566c_bia_stage14_scalable_font.py) · [source](../history/sources/project/f9f1fa99190170b4_capture_ppsspp.ps1) |
| STAGE14B | 4 | 명시 없음/코드만 있음 | [report](../history/evidence/project/d7112d1be3742ad9_stage14b_report.json) · [source](../history/sources/project/87e0c03679596516_bia_stage14b_scalable_font.py) |
| STAGE15 | 4 | 명시 없음/코드만 있음 | [report](../history/evidence/project/a4c2a8a4f6640bab_stage15_report.json) · [source](../history/sources/project/053875793e599898_bia_stage15_expanded_atlas.py) |
| STAGE16 | 4 | 명시 없음/코드만 있음 | [report](../history/evidence/project/5353627f36cd00ab_stage16_report.json) · [source](../history/sources/project/df10fba33a078854_bia_stage16_disc_native_font.py) |
| STAGE17 | 4 | 명시 없음/코드만 있음 | [report](../history/evidence/project/3f2a6fe6c56a6e21_stage17_report.json) · [source](../history/sources/project/eedc6c4411ca9b0a_bia_stage17_texture_runtime_trace.py) |
| STAGE18 | 3 | 명시 없음/코드만 있음 | [source](../history/sources/project/cd1427e1a14e24cd_bia_stage18_gpu_frame_dump.py) · [source](../history/sources/project/f9f1fa99190170b4_capture_ppsspp.ps1) |
| STAGE18B | 3 | 명시 없음/코드만 있음 | [source](../history/sources/project/b2f12e98fdf398e1_bia_stage18b_gpu_frame_dump.py) · [source](../history/sources/project/f9f1fa99190170b4_capture_ppsspp.ps1) |
| STAGE18C | 4 | 명시 없음/코드만 있음 | [report](../history/evidence/project/a6755678d06beb26_stage18c_report.json) · [source](../history/sources/project/de7bf4c888f8bd3f_bia_stage18c_gpu_frame_dump.py) |
| STAGE19 | 3 | 명시 없음/코드만 있음 | [source](../history/sources/project/bb33b0000a9f1e74_bia_stage19_disc_expanded_tmr.py) · [source](../history/sources/project/f9f1fa99190170b4_capture_ppsspp.ps1) |
| STAGE19B | 3 | 명시 없음/코드만 있음 | [source](../history/sources/project/f3f4cb949d024e0c_bia_stage19b_disc_expanded_tmr.py) · [source](../history/sources/project/f9f1fa99190170b4_capture_ppsspp.ps1) |
| STAGE19C | 3 | 명시 없음/코드만 있음 | [source](../history/sources/project/471b55df0a586b55_bia_stage19c_disc_expanded_tmr.py) · [source](../history/sources/project/f9f1fa99190170b4_capture_ppsspp.ps1) |
| STAGE20 | 4 | 명시 없음/코드만 있음 | [report](../history/evidence/project/ae1b3d2f337b7e79_stage20_report.json) · [source](../history/sources/project/c87acd1fcbc8f8df_bia_stage20_mdi_texture.py) |
| STAGE21 | 3 | 명시 없음/코드만 있음 | [source](../history/sources/project/fa37812d84febd8a_bia_stage21_relocated_descriptor.py) · [source](../history/sources/project/f9f1fa99190170b4_capture_ppsspp.ps1) |
| STAGE22 | 3 | 명시 없음/코드만 있음 | [source](../history/sources/project/c236affa0db63909_bia_stage22_runtime_descriptor_patch.py) · [source](../history/sources/project/f9f1fa99190170b4_capture_ppsspp.ps1) |
| STAGE22B | 3 | 명시 없음/코드만 있음 | [source](../history/sources/project/4013d2b939e57376_bia_stage22b_runtime_descriptor_patc.py) · [source](../history/sources/project/f9f1fa99190170b4_capture_ppsspp.ps1) |
| STAGE22C | 4 | 명시 없음/코드만 있음 | [report](../history/evidence/project/5138cea212b74747_stage22c_report.json) · [source](../history/sources/project/5a25004e520c1c3a_bia_stage22c_runtime_descriptor_patc.py) |
| STAGE23 | 3 | 명시 없음/코드만 있음 | [source](../history/sources/project/7f5e138cca44f5ae_bia_stage23_live_ge_patch.py) · [source](../history/sources/project/f9f1fa99190170b4_capture_ppsspp.ps1) |
| STAGE24 | 5 | 명시 없음/코드만 있음 | [report](../history/evidence/project/cf552c229231affd_stage24_report.json) · [report](../history/evidence/project/2a855797ddcfde61_stage24_runtime_inventory.json) |
| STAGE25 | 3 | 명시 없음/코드만 있음 | [source](../history/sources/project/6aaebda779fa9dbe_bia_stage25_tools_bia_stage25_frame_.py) · [source](../history/sources/project/f9f1fa99190170b4_capture_ppsspp.ps1) |
| STAGE25B | 5 | 명시 없음/코드만 있음 | [report](../history/evidence/project/4fda6ac16883a482_stage25b_report.json) · [report](../history/evidence/project/2a855797ddcfde61_stage24_runtime_inventory.json) |
| STAGE26 | 5 | 명시 없음/코드만 있음 | [report](../history/evidence/project/b2fca6e0caef6f75_stage26_report.json) · [report](../history/evidence/project/2a855797ddcfde61_stage24_runtime_inventory.json) |
| STAGE27 | 3 | 명시 없음/코드만 있음 | [source](../history/sources/project/8ab316f882e4cfbd_bia_stage27_tools_bia_stage27_descri.py) · [source](../history/sources/project/f9f1fa99190170b4_capture_ppsspp.ps1) |
| STAGE27B | 3 | 명시 없음/코드만 있음 | [source](../history/sources/project/816389e61022b80a_bia_stage27b_tools_bia_stage27b_desc.py) · [source](../history/sources/project/f9f1fa99190170b4_capture_ppsspp.ps1) |
| STAGE27C | 4 | 명시 없음/코드만 있음 | [report](../history/evidence/project/6f111acb58e715a1_stage27c_report.json) · [source](../history/sources/project/4a86ba0aaf079b9b_bia_stage27c_tools_bia_stage27c_desc.py) |
| STAGE28 | 3 | 명시 없음/코드만 있음 | [source](../history/sources/project/8e42277f6a27304d_bia_stage28_tools_bia_stage28_condit.py) · [source](../history/sources/project/f9f1fa99190170b4_capture_ppsspp.ps1) |
| STAGE28B | 4 | 명시 없음/코드만 있음 | [report](../history/evidence/project/9340539db87bac88_stage28b_report.json) · [source](../history/sources/project/23694f8acf5e19ce_bia_stage28b_conditional_writer_brea.py) |
| STAGE29 | 4 | 명시 없음/코드만 있음 | [report](../history/evidence/project/d214fdae0c633d74_stage29_report.json) · [source](../history/sources/project/6574dde871bf403e_bia_stage29_relocation_entry_trace.py) |
| STAGE30 | 4 | 명시 없음/코드만 있음 | [report](../history/evidence/project/1f7d0ff445de7088_stage30_report.json) · [source](../history/sources/project/306b828d20551d91_bia_stage30_tmr_relocation_entry.py) |
| STAGE31 | 3 | 명시 없음/코드만 있음 | [source](../history/sources/project/2a58471940e16aff_bia_stage31_tools_bia_stage31_perman.py) · [source](../history/sources/project/f9f1fa99190170b4_capture_ppsspp.ps1) |
| STAGE32 | 4 | 명시 없음/코드만 있음 | [report](../history/evidence/project/9d5a7ce8e3027f51_stage32_report.json) · [source](../history/sources/project/4bb1a3aba60de31e_bia_stage32_tools_bia_stage32_perman.py) |
| STAGE33 | 4 | 명시 없음/코드만 있음 | [report](../history/evidence/project/394f0c679a87f431_stage33_report.json) · [source](../history/sources/project/45e8a988186be7d4_bia_stage33_tools_bia_stage33_scalab.py) |
| STAGE34 | 4 | 명시 없음/코드만 있음 | [report](../history/evidence/project/d31562737ac540b8_stage34_report.json) · [source](../history/sources/project/47f30dc54443b876_bia_stage34_tools_bia_stage34_gpu_uv.py) |
| STAGE35 | 3 | 명시 없음/코드만 있음 | [source](../history/sources/project/adea46f00a51d44f_bia_stage35_tools_bia_stage35_render.py) · [source](../history/sources/project/f9f1fa99190170b4_capture_ppsspp.ps1) |
| STAGE37 | 3 | 명시 없음/코드만 있음 | [report](../history/evidence/project/222ada19222862ef_stage37_summary.json) · [source](../history/sources/project/27d8f53329849478_bia_stage37_corpus_inventory.py) |
| STAGE38 | 3 | 명시 없음/코드만 있음 | [report](../history/evidence/project/36ff0e59e6c9c0e0_stage38_summary.json) · [source](../history/sources/project/aff2c9adb0b85899_bia_stage38_translation_worklist.py) |
| STAGE38B | 3 | 명시 없음/코드만 있음 | [report](../history/evidence/project/9f727fea433123a7_stage38b_summary.json) · [source](../history/sources/project/749b250a69f18620_bia_stage38b_tools_bia_stage38b_tran.py) |
| STAGE39A | 5 | 명시 없음/코드만 있음 | [report](../history/evidence/project/27c8b6a3d78f1111_stage39a_report.json) · [source](../history/sources/project/380ff1bd7469ee2e_bia_stage39a_tools_bia_stage36_base.py) |
| STAGE39B | 6 | 명시 없음/코드만 있음 | [report](../history/evidence/project/42aaba477426e610_stage39b_report.json) · [source](../history/sources/project/380ff1bd7469ee2e_bia_stage39a_tools_bia_stage36_base.py) |
| STAGE39D | 4 | 명시 없음/코드만 있음 | [report](../history/evidence/project/421641a2c25890de_stage39d_report.json) · [report](../history/evidence/project/83c1e1aae53922ae_stage39d_patch_manifest.json) |
| STAGE39E | 3 | 명시 없음/코드만 있음 | [report](../history/evidence/project/d424db96df30290f_stage39e_report.json) · [source](../history/sources/project/a582e629641906d7_bia_stage39e_widen_writer_trace.py) |
| STAGE39F | 3 | 명시 없음/코드만 있음 | [report](../history/evidence/project/7d8737d595540093_stage39f_report.json) · [source](../history/sources/project/18daaab8fe76ac01_bia_stage39f_tools_bia_stage39f_corr.py) |
| STAGE39G | 3 | 명시 없음/코드만 있음 | [report](../history/evidence/project/774a5850d6b5ce4f_stage39g_report.json) · [source](../history/sources/project/567be90884e5cfa5_bia_stage39g_external_ram_proof.py) |
| STAGE39H | 3 | 명시 없음/코드만 있음 | [report](../history/evidence/project/7e377b7bc7c11f5f_stage39h_report.json) · [source](../history/sources/project/adc37d7c9843f6b8_bia_stage39h_tools_bia_stage39h_main.py) |
| STAGE39I | 3 | 명시 없음/코드만 있음 | [report](../history/evidence/project/373a988f40ed63e8_stage39i_report.json) · [source](../history/sources/project/3fe922f5a25a0319_bia_stage39i_render_path_trace.py) |
| STAGE39J | 3 | 명시 없음/코드만 있음 | [report](../history/evidence/project/2da068a611392fd7_stage39j_report.json) · [source](../history/sources/project/b5ba4278450174ee_bia_stage39j_glyph_render_trace.py) |
| STAGE39K | 3 | 명시 없음/코드만 있음 | [report](../history/evidence/project/21089cc94b617b43_stage39k_report.json) · [source](../history/sources/project/7480fed9b29d0ac1_bia_stage39k_visible_narrow_renderer.py) |
| STAGE39L | 3 | 명시 없음/코드만 있음 | [report](../history/evidence/project/0748e3dd41c998d4_stage39l_report.json) · [source](../history/sources/project/829edea84df953ce_bia_stage39l_dual_renderer_trace.py) |
| STAGE39M | 3 | 명시 없음/코드만 있음 | [report](../history/evidence/project/915f3cbde89b849d_stage39m_report.json) · [source](../history/sources/project/f1a2af7f7e65169e_bia_stage39m_visible_vertex_writer.py) |
| STAGE39N | 3 | 명시 없음/코드만 있음 | [report](../history/evidence/project/cfb837fa19afdeb4_stage39n_report.json) · [source](../history/sources/project/6280a78f8c2fc55d_bia_stage39n_masked_vertex_writer.py) |
| STAGE39O | 3 | 명시 없음/코드만 있음 | [report](../history/evidence/project/59e41e9702387f44_stage39o_report.json) · [source](../history/sources/project/ca318c91e148e000_bia_stage39o_frozen_vertex_writer.py) |
| STAGE39P | 3 | 명시 없음/코드만 있음 | [report](../history/evidence/project/829ca495df6e68c4_stage39p_report.json) · [source](../history/sources/project/0ddff382eccdd344_bia_stage39p_draw_helper_trace.py) |
| STAGE39Q | 3 | 명시 없음/코드만 있음 | [report](../history/evidence/project/8eadd60996a0df8c_stage39q_report.json) · [source](../history/sources/project/24648e5202604b6c_bia_stage39q_settled_draw_trace.py) |
| STAGE39R | 3 | 명시 없음/코드만 있음 | [report](../history/evidence/project/04cb27b1aa75160f_stage39r_report.json) · [source](../history/sources/project/a5ac92fc03b4bf0a_bia_stage39r_confirmed_menu_draw_tra.py) |
| STAGE39S | 3 | 명시 없음/코드만 있음 | [report](../history/evidence/project/4d5dfab813af39a2_stage39s_patch_manifest.json) · [source](../history/sources/project/ba0a63d77decf382_bia_stage39s_tools.zip_bia_stage39s_.py) |
| STAGE39T | 3 | 명시 없음/코드만 있음 | [report](../history/evidence/project/da4f0e16ceadf075_stage39t_patch_manifest.json) · [source](../history/sources/project/056f25c084029d55_bia_stage39t_boot_renderer_utf8.py) |
| STAGE39U | 8 | 명시 없음/코드만 있음 | [report](../history/evidence/project/bd648f4c1a633d1c_stage39u_report.json) · [report](../history/evidence/project/84b3c67a8677fcc5_stage39u_patch_manifest.json) |
| STAGE40A | 31 | 명시 없음/코드만 있음 | [report](../history/evidence/project/573d2500ec0c9b22_stage40a_asset_inventory.json) · [report](../history/evidence/project/27c8b6a3d78f1111_stage39a_report.json) |
| STAGE40B | 3 | 명시 없음/코드만 있음 | [report](../history/evidence/project/9d0a72edc809a4b1_stage40b_manifest.json) · [source](../history/sources/project/db0842eea24d390f_bia_stage40b_a_mass_insert.py) |
| STAGE40C | 9 | 명시 없음/코드만 있음 | [report](../history/evidence/project/6671ea75023d0a6f_stage40c_report.json) · [report](../history/evidence/project/0b6fa2c2e7084e76_stage40c_manifest.json) |
| STAGE40D | 4 | 명시 없음/코드만 있음 | [report](../history/evidence/project/e0cde3e62a4b4244_stage40d_report.json) · [report](../history/evidence/project/a9846d682203c2c3_stage40d_manifest.json) |
| STAGE40E | 4 | 명시 없음/코드만 있음 | [report](../history/evidence/project/d08dcc86b5523e5e_stage40e_report.json) · [report](../history/evidence/project/cdf64b4fb749e052_stage40e_manifest.json) |
| STAGE40F | 8 | 명시 없음/코드만 있음 | [report](../history/evidence/project/bb02437ea3b91dea_stage40f_report.json) · [report](../history/evidence/project/b63d693cd74ec7c1_stage40f_manifest.json) |
| STAGE40G | 4 | 명시 없음/코드만 있음 | [report](../history/evidence/project/239ad53fb5e19a57_stage40g_report.json) · [report](../history/evidence/project/26d1f74e3ddf97ba_stage40g_manifest.json) |
| STAGE40H | 7 | 명시 없음/코드만 있음 | [report](../history/evidence/project/886321829cd8e0fc_stage40h_retry_report.json) · [report](../history/evidence/project/a58a0a469c847df9_stage40h_retry_manifest.json) |
| STAGE40I | 7 | 명시 없음/코드만 있음 | [report](../history/evidence/project/97f39d5b8c6e3ffe_stage40i_report.json) · [report](../history/evidence/project/5e3805ef4e06c694_stage40i_manifest.json) |
| STAGE40J | 7 | runtime_verified=False; runtime_verified=True | [report](../history/evidence/session-outputs/591c0bc87b90c8c9_key_restore_report.json) · [report](../history/evidence/session-outputs/35e9ff167b2a1d7e_ram_read_report.json) |
| STAGE40K | 6 | runtime_verified=False; runtime_verified=True | [report](../history/evidence/session-outputs/1cb86085fd654c03_font_patch_report.json) · [report](../history/evidence/session-outputs/35e9ff167b2a1d7e_ram_read_report.json) |
| STAGE40L | 5 | runtime_verified=False | [report](../history/evidence/session-outputs/f206215a4c7ed01a_width_patch_report.json) · [report](../history/evidence/session-outputs/35e9ff167b2a1d7e_ram_read_report.json) |
| STAGE40M | 3 | runtime_verified=False | [report](../history/evidence/session-outputs/e8631a3cdb173abf_ui_additions_report.json) · [report](../history/evidence/session-outputs/35e9ff167b2a1d7e_ram_read_report.json) |
| STAGE40N | 1 | 명시 없음/코드만 있음 | [source](../history/sources/session-work/e210404b30c3ecc8_stage40n_live.py) |
| STAGE40O | 11 | runtime_verified=False; runtime_verified=True | [report](../history/evidence/session-outputs/e3370c678d636afb_width_patch_report.json) · [report](../history/evidence/session-outputs/35e9ff167b2a1d7e_ram_read_report.json) |
| STAGE40P | 2 | 명시 없음/코드만 있음 | [report](../history/evidence/session-outputs/35e9ff167b2a1d7e_ram_read_report.json) · [source](../history/sources/session-work/fb3ce60862d85c52_stage40p_live.py) |
| STAGE40Q | 2 | 명시 없음/코드만 있음 | [report](../history/evidence/session-outputs/35e9ff167b2a1d7e_ram_read_report.json) · [source](../history/sources/session-work/f71ad5c3bc6b3eb9_stage40q_live.py) |
| STAGE40R | 3 | runtime_verified=False | [report](../history/evidence/session-outputs/1a3c16837c48905c_campaign_renderer_patch_report.json) · [report](../history/evidence/session-outputs/35e9ff167b2a1d7e_ram_read_report.json) |
| STAGE40S | 4 | runtime_verified=False; status=failed_runtime_validation | [report](../history/evidence/session-outputs/91c639a19e674db3_first_mission_patch_report.json) · [report](../history/evidence/session-outputs/35e9ff167b2a1d7e_ram_read_report.json) |
| STAGE40T | 3 | runtime_verified=False | [report](../history/evidence/session-outputs/cb8bd9b3dc3a0992_first_mission_patch_report.json) · [report](../history/evidence/session-outputs/35e9ff167b2a1d7e_ram_read_report.json) |
| STAGE40U | 1 | runtime_verified=False | [report](../history/evidence/session-outputs/22153695c7532dd5_first_mission_patch_report.json) |
| STAGE40V | 1 | runtime_verified=False | [report](../history/evidence/session-outputs/a3b20161fe809f7e_first_mission_patch_report.json) |
| STAGE40W | 3 | runtime_verified=False | [report](../history/evidence/session-outputs/c4933bb1c03fe71c_first_mission_patch_report.json) · [report](../history/evidence/session-outputs/35e9ff167b2a1d7e_ram_read_report.json) |
| STAGE40X | 1 | runtime_verified=False | [report](../history/evidence/session-outputs/57200038595f447f_first_mission_patch_report.json) |
| STAGE40Y | 5 | runtime_verified=False; runtime_verified=True | [report](../history/evidence/session-outputs/be488dd96099bb67_first_mission_patch_report.json) · [report](../history/evidence/session-outputs/1ea6085a207a030a_quit_input_results.json) |
| STAGE40Z | 4 | 명시 없음/코드만 있음 | [report](../history/evidence/project/048fa4b755717dd7_stage40z_report.json) · [report](../history/evidence/project/de13fa4249976157_stage40z_manifest.json) |
| STAGE40Z FIX1 | 4 | 명시 없음/코드만 있음 | [report](../history/evidence/project/e9956fa25a57cfbb_stage40z_fix1_report.json) · [report](../history/evidence/project/990ce6863c6c5e34_stage40z_fix1_manifest.json) |
| STAGE40Z FIX2 | 4 | 명시 없음/코드만 있음 | [report](../history/evidence/project/01d1ace044aeb590_stage40z_fix2_report.json) · [report](../history/evidence/project/c654d69a0620d88b_stage40z_fix2_manifest.json) |
| STAGE40Z FIX3 | 4 | 명시 없음/코드만 있음 | [report](../history/evidence/project/334dd725e23a7174_stage40z_fix3_report.json) · [report](../history/evidence/project/a51c2bd738bb1487_stage40z_fix3_manifest.json) |
| STAGE40Z FIX4 | 4 | 명시 없음/코드만 있음 | [report](../history/evidence/project/6b2e359a73c6ea64_stage40z_fix4_report.json) · [report](../history/evidence/project/a964f28796ff6683_stage40z_fix4_manifest.json) |
| STAGE41A | 4 | 명시 없음/코드만 있음 | [report](../history/evidence/project/de22cf2b0e42db9b_stage41a_report.json) · [report](../history/evidence/project/1a226a7e409f4631_stage41a_manifest.json) |
| STAGE41B | 3 | error=RuntimeError('Korean ST1 buffer was not found within timeout.') | [report](../history/evidence/project/c1683c5097cf6424_stage41b_report.json) · [source](../history/sources/project/e5400e34e57de701_run_bia_stage41b.ps1) |
| STAGE41B FIX1 | 3 | error=RuntimeError('Korean ST1 buffer was not found. Automatic route may have missed; no memory.sear | [report](../history/evidence/project/a9ab7be91b8774e9_stage41b_fix1_report.json) · [source](../history/sources/project/5a0271214e67db62_run_bia_stage41b_fix1.ps1) |
| STAGE41B FIX2 | 3 | error=RuntimeError('ST1 loaded, but no read watchpoint hits were captured.') | [report](../history/evidence/project/21566764ba9539d5_stage41b_fix2_report.json) · [source](../history/sources/project/39255f09d6da1767_run_bia_stage41b_fix2.ps1) |
| STAGE41B FIX3 | 3 | error=RuntimeError('ST1 loaded successfully, but no read-watchpoint hits were observed.') | [report](../history/evidence/project/6dc3eb278619e6b3_stage41b_fix3_report.json) · [source](../history/sources/project/c1e8c40ac8fcf9c8_run_bia_stage41b_fix3.ps1) |
| STAGE41B FIX4 | 3 | error=RuntimeError('ST1 loaded but no R/W watchpoint event was emitted even though watchpoints were  | [report](../history/evidence/project/5e2c1bff2739107b_stage41b_fix4_report.json) · [source](../history/sources/project/bbdd543515e8de42_run_bia_stage41b_fix4.ps1) |
| STAGE41B FIX5 | 3 | error=RuntimeError('No memory breakpoint PC event captured. Breakpoint-list hit counters are preserv | [report](../history/evidence/project/b076c44e29b0f8f6_stage41b_fix5_report.json) · [source](../history/sources/project/96716370d3f76d37_run_bia_stage41b_fix5.ps1) |
| STAGE41B FIX6 | 3 | 명시 없음/코드만 있음 | [report](../history/evidence/project/3d981714d531f814_stage41b_fix6_report.json) · [source](../history/sources/project/0ff6ac946b58bf34_run_bia_stage41b_fix6.ps1) |
| STAGE41C | 2 | 명시 없음/코드만 있음 | [source](../history/sources/project/5bd7b0b16ef7aedf_run_bia_stage41c.ps1) · [source](../history/sources/project/378412095a9c61e6_stage41c_bink_parser_unwind.py) |
| STAGE41D | 4 | 명시 없음/코드만 있음 | [report](../history/evidence/project/1305c0702c5feab1_stage41d_report.json) · [source](../history/sources/project/3fe284cf2aa9fc7b_run_bia_stage41d.ps1) |
| STAGE41E | 6 | 명시 없음/코드만 있음 | [report](../history/evidence/project/4369770cf2f85979_stage41e_build_report.json) · [report](../history/evidence/project/b57a46b81238f4e4_stage41e_test_report.json) |
| STAGE41E FIX1 | 3 | 명시 없음/코드만 있음 | [report](../history/evidence/project/844038cc5d663d7d_stage41e_fix1_report.json) · [source](../history/sources/project/db327d298ce47726_run_bia_stage41e_fix1.ps1) |
| STAGE41F | 12 | error=RuntimeError('automatic route failed') | [report](../history/evidence/project/3cf903c04f38a54b_stage41f_autoentry_diag_report.json) · [report](../history/evidence/project/37caff7141479deb_stage41f_autoentry_fix1_report.json) |
| STAGE42A | 3 | 명시 없음/코드만 있음 | [report](../history/evidence/project/d2ea7d1182cc0d95_stage42a_report.json) · [source](../history/sources/project/dc038d069f8aa57e_run_bia_stage42a.ps1) |
| STAGE42B | 7 | 명시 없음/코드만 있음 | [report](../history/evidence/project/37c4a90e0cdabcae_stage42b_build_report.json) · [report](../history/evidence/project/e4c93f9cb39e3e91_stage42b_probe_report.json) |
| STAGE42C | 6 | 명시 없음/코드만 있음 | [report](../history/evidence/project/940587069ecf42f4_stage42c_build_report.json) · [report](../history/evidence/project/da437557be895cc7_stage42c_report.json) |
| STAGE42D | 6 | 명시 없음/코드만 있음 | [report](../history/evidence/project/cfb88b323e71d75a_stage42d_build_report.json) · [report](../history/evidence/project/29530f914fcd16ad_stage42d_report.json) |
| STAGE42E | 6 | 명시 없음/코드만 있음 | [report](../history/evidence/project/0d243cee5a1c981d_stage42e_build_report.json) · [report](../history/evidence/project/beb647061e6fcffb_stage42e_report.json) |
| STAGE42F | 6 | 명시 없음/코드만 있음 | [report](../history/evidence/project/6cecd9809af3012b_stage42f_build_report.json) · [report](../history/evidence/project/cced18fb46fb2639_stage42f_report.json) |
| STAGE42G | 8 | 명시 없음/코드만 있음 | [report](../history/evidence/project/ec212f0fc412e03e_stage42g_build_report.json) · [report](../history/evidence/project/66650426d4d13fcf_stage42g_report.json) |
| STAGE42G FIX1 | 3 | 명시 없음/코드만 있음 | [source](../history/sources/project/b3a717b6d5370e79_run_bia_stage42g_fix1.ps1) · [source](../history/sources/project/35a033bfc6442433_stage42g_fix1_texture_trace.py) |
| STAGE42G FIX10 | 2 | 명시 없음/코드만 있음 | [source](../history/sources/project/f09109193dccaf72_run_bia_stage42g_fix10.ps1) · [source](../history/sources/project/8103786114b67b83_stage42g_fix10_register512.py) |
| STAGE42G FIX11 | 2 | 명시 없음/코드만 있음 | [source](../history/sources/project/7287ca9ecef0265f_run_bia_stage42g_fix11.ps1) · [source](../history/sources/project/5f9158957f1f4143_stage42g_fix11_register512.py) |
| STAGE42G FIX12 | 4 | 명시 없음/코드만 있음 | [report](../history/evidence/project/e12c858d317e3f11_stage42g_fix12_manifest.json) · [source](../history/sources/project/67c3247a78e5d30a_build_stage42g_fix12.py) |
| STAGE42G FIX13 | 2 | 명시 없음/코드만 있음 | [source](../history/sources/project/60539d85cc10815f_run_bia_stage42g_fix13.ps1) · [source](../history/sources/project/2c44e4e8bdc9df82_stage42g_fix13_texture_ram_verify.py) |
| STAGE42G FIX14 | 2 | 명시 없음/코드만 있음 | [source](../history/sources/project/2db93f1338e3a332_run_bia_stage42g_fix14.ps1) · [source](../history/sources/project/20028541d7ca6b03_stage42g_fix14_texture_lifetime.py) |
| STAGE42G FIX15 | 2 | 명시 없음/코드만 있음 | [source](../history/sources/project/d716db96fc900116_run_bia_stage42g_fix15.ps1) · [source](../history/sources/project/da06e1d5be08f5e2_stage42g_fix15_render_trace.py) |
| STAGE42G FIX16 | 2 | 명시 없음/코드만 있음 | [source](../history/sources/project/9dc7ad846fa99d2a_run_bia_stage42g_fix16.ps1) · [source](../history/sources/project/ba88c8f3c54c1b70_stage42g_fix16_ge_live_trace.py) |
| STAGE42G FIX17 | 3 | 명시 없음/코드만 있음 | [report](../history/evidence/project/0c43db192837b86b_stage42g_fix17_local_report.json) · [source](../history/sources/project/9c3388a6fd747c38_run_bia_stage42g_fix17_local.ps1) |
| STAGE42G FIX18 | 3 | 명시 없음/코드만 있음 | [report](../history/evidence/project/7627ca23749f56d1_stage42g_fix18_local_report.json) · [source](../history/sources/project/4bd5711124c1ff5c_run_bia_stage42g_fix18_local.ps1) |
| STAGE42G FIX19 | 3 | 명시 없음/코드만 있음 | [report](../history/evidence/project/e0414f8c311eebfd_stage42g_fix19_local_report.json) · [source](../history/sources/project/22d8a2469258053b_run_bia_stage42g_fix19_local.ps1) |
| STAGE42G FIX2 | 3 | 명시 없음/코드만 있음 | [source](../history/sources/project/14756f16e4a327ff_run_bia_stage42g_fix2.ps1) · [source](../history/sources/project/7ba1509876b88df1_stage42g_fix2_deep_trace.py) |
| STAGE42G FIX3 | 3 | 명시 없음/코드만 있음 | [source](../history/sources/project/a10d8d00972d5f3b_build_stage42g_fix3.py) · [source](../history/sources/project/0615ad56ab686731_run_bia_stage42g_fix3.ps1) |
| STAGE42G FIX4 | 3 | error=RuntimeError('Unexpected runtime dimension words: H=0x8C857CEC W=0x0E24920C') | [report](../history/evidence/project/31a25c19192d6917_stage42g_fix4_report.json) · [source](../history/sources/project/d6849654826b3e1c_run_bia_stage42g_fix4.ps1) |
| STAGE42G FIX5 | 2 | 명시 없음/코드만 있음 | [source](../history/sources/project/3ebae711126eb6cd_run_bia_stage42g_fix5.ps1) · [source](../history/sources/project/47199b3d383b68c5_stage42g_fix5_register512.py) |
| STAGE42G FIX6 | 3 | error=RuntimeError('debugger unavailable') | [report](../history/evidence/project/f340e966634b6b47_stage42g_fix6_report.json) · [source](../history/sources/project/027c4fc8404034c3_run_bia_stage42g_fix6.ps1) |
| STAGE42G FIX7 | 2 | 명시 없음/코드만 있음 | [source](../history/sources/project/26b5e2417eee0edf_run_bia_stage42g_fix7.ps1) · [source](../history/sources/project/988f94a9307b2f6b_stage42g_fix7_register512.py) |
| STAGE42G FIX8 | 2 | 명시 없음/코드만 있음 | [source](../history/sources/project/4c413e0d4c7da698_run_bia_stage42g_fix8.ps1) · [source](../history/sources/project/a2cc06316707b828_stage42g_fix8_register512.py) |
| STAGE42G FIX9 | 3 | 명시 없음/코드만 있음 | [report](../history/evidence/project/9f2dd0b0bf827ced_stage42g_fix16_report.json) · [source](../history/sources/project/9e2010782064e806_run_bia_stage42g_fix9.ps1) |
| STAGE42H | 8 | runtime_verified=True | [report](../history/evidence/project/f809b484a65d1c54_stage42g_stage42h_resume_report.json) · [report](../history/evidence/project/1bc9a7122ec17916_bookends_probe_alias_report.json) |
| STAGE42I | 2 | 명시 없음/코드만 있음 | [source](../history/sources/project/6b79316f8cf38b5a_run_stage42i_movie.ps1) · [source](../history/sources/project/b100cccbf06923c6_stage42i_runtime.py) |
| STAGE43A | 3 | runtime_verified=False | [report](../history/evidence/session-outputs/4f8b4738ddb1ff1d_campaign_patch_report.json) · [report](../history/evidence/session-outputs/35e9ff167b2a1d7e_ram_read_report.json) |
| STAGE43B | 4 | 명시 없음/코드만 있음 | [report](../history/evidence/session-outputs/f16cc8dfc46b2205_hud_font_inventory.json) · [report](../history/evidence/session-outputs/35e9ff167b2a1d7e_ram_read_report.json) |
| STAGE43C | 2 | 명시 없음/코드만 있음 | [report](../history/evidence/session-outputs/35e9ff167b2a1d7e_ram_read_report.json) · [source](../history/sources/session-work/ed3af8da73889375_stage43c_live.py) |
| STAGE43D | 1 | runtime_verified=False | [report](../history/evidence/session-outputs/81d24e7841826da1_ufont_expansion_report.json) |
| STAGE43E | 2 | runtime_verified=False | [report](../history/evidence/session-outputs/ea7d9b4170448ba1_utf8_render_patch_report.json) · [source](../history/sources/session-work/52de4d41dbc4f52d_stage43e_live.py) |
| STAGE43F | 3 | runtime_verified=False | [report](../history/evidence/session-outputs/65a2bd9593ae52d5_safe_code_patch_report.json) · [report](../history/evidence/session-outputs/35e9ff167b2a1d7e_ram_read_report.json) |
| STAGE43G | 2 | runtime_verified=False | [report](../history/evidence/session-outputs/ab8536c227b61ee3_texture_clone_report.json) · [source](../history/sources/session-work/e290c2b5cfce5150_stage43g_live.py) |
| STAGE43H | 3 | runtime_verified=True | [report](../history/evidence/session-outputs/c44dc1e7b7b5da1c_font_report.json) · [report](../history/evidence/session-outputs/6e393c9ea41727a3_second_mission_reference_report.json) |
| STAGE43I | 2 | runtime_verified=True | [report](../history/evidence/session-outputs/1b9008f9d0e33b73_hint_fit_report.json) · [source](../history/sources/session-work/8ec179d832373d91_stage43i_live.py) |
| STAGE43J | 2 | 명시 없음/코드만 있음 | [report](../history/evidence/session-outputs/35e9ff167b2a1d7e_ram_read_report.json) · [source](../history/sources/session-work/e38b88debcfcd737_stage43j_live.py) |
| STAGE43K | 3 | 명시 없음/코드만 있음 | [report](../history/evidence/session-outputs/890ee2c1d43b18ad_font_inventory_relaxed.json) · [report](../history/evidence/session-outputs/35e9ff167b2a1d7e_ram_read_report.json) |
| STAGE43L | 2 | runtime_verified=False | [report](../history/evidence/session-outputs/bd680b092a558b0d_objective_patch_report.json) · [source](../history/sources/session-work/c611f5e7b62924e9_stage43l_live.py) |
| STAGE43M | 2 | runtime_verified=True | [report](../history/evidence/session-outputs/bdf053899e2bb216_objective_patch_report.json) · [source](../history/sources/session-work/38cd60975625c234_stage43m_live.py) |
| STAGE43N | 5 | 명시 없음/코드만 있음 | [report](../history/evidence/session-outputs/35e9ff167b2a1d7e_ram_read_report.json) · [report](../history/evidence/session-outputs/35e9ff167b2a1d7e_ram_read_report.json) |
| STAGE43O | 6 | runtime_verified=True | [report](../history/evidence/session-outputs/20b51462e0edb7d7_restart_patch_report.json) · [report](../history/evidence/session-outputs/35e9ff167b2a1d7e_ram_read_report.json) |
| STAGE43P | 4 | 명시 없음/코드만 있음 | [report](../history/evidence/session-outputs/35e9ff167b2a1d7e_ram_read_report.json) · [report](../history/evidence/session-outputs/1b0dcd83ac0b96a9_restart_probe_status_regs.json) |
| STAGE43Q | 3 | runtime_verified=True | [report](../history/evidence/session-outputs/0dd297c8bb3b4e98_patch_report.json) · [report](../history/evidence/session-outputs/35e9ff167b2a1d7e_ram_read_report.json) |
| STAGE43R | 8 | 명시 없음/코드만 있음 | [report](../history/evidence/session-outputs/35e9ff167b2a1d7e_ram_read_report.json) · [report](../history/evidence/session-outputs/35e9ff167b2a1d7e_ram_read_report.json) |
| STAGE43S | 3 | runtime_verified=False | [report](../history/evidence/session-outputs/8ff4ecb0775f9e49_patch_report.json) · [report](../history/evidence/session-outputs/35e9ff167b2a1d7e_ram_read_report.json) |
| STAGE43T | 3 | runtime_verified=True | [report](../history/evidence/session-outputs/63596d77f94faebc_patch_report.json) · [report](../history/evidence/session-outputs/35e9ff167b2a1d7e_ram_read_report.json) |
| STAGE97 | 1 | 명시 없음/코드만 있음 | [source](../history/sources/session-work/0a12b6a367cbc616_stage097_live.py) |
| STAGE98 | 1 | 명시 없음/코드만 있음 | [source](../history/sources/session-work/f6803c531c061bbc_stage098_live.py) |
| STEP40 | 3 | 명시 없음/코드만 있음 | [source](../history/sources/session-work/8446431e4a5e8082_build_font40k.py) · [source](../history/sources/session-work/0344b85687825b17_offline_font40k.py) |
| STEP43 | 32 | 명시 없음/코드만 있음 | [source](../history/sources/project/c00293af0086a2f9_16_audit43m_title.py) · [source](../history/sources/session-work/8a1be70bf709c526_audit43r_title.py) |
| STEP44 | 27 | 명시 없음/코드만 있음 | [report](../history/evidence/project/dde7eb3eb24177db_candidate_inventory.json) · [note](../history/evidence/project/bde9c1ab0e1a7286_PROJECT_STATE.md) |
| STEP44 FIX5 | 4 | 명시 없음/코드만 있음 | [note](../history/evidence/project/9b7d92ea0c31fccd_PROJECT_STATE.md) · [source](../history/sources/project/d62e16d86c68ceb6_discover_campaign_fix5.py) |
| STEP44 FIX6 | 33 | 명시 없음/코드만 있음 | [report](../history/evidence/project/256bd6c84183595c_candidate_inventory.json) · [note](../history/evidence/project/5c4cbb534ddfc8df_PROJECT_STATE.md) |
| STEP44 FIX7 | 4 | 명시 없음/코드만 있음 | [note](../history/evidence/project/d4de2df683fce30d_PROJECT_STATE.md) · [source](../history/sources/project/e769f19145320fa5_extract_next_campaign.py) |
| STEP45 | 11 | 명시 없음/코드만 있음 | [report](../history/evidence/project/5d3270f0dbbbe3ed_translation_review_report.json) · [report](../history/evidence/project/120163f0c3bf87f1_step045_apply_report.json) |
| STEP46 | 11 | 명시 없음/코드만 있음 | [report](../history/evidence/project/a336e94ca5978a3e_translation_review_report.json) · [report](../history/evidence/project/fd26f8af3b67ed3c_step046_report.json) |
| STEP47 | 11 | 명시 없음/코드만 있음 | [report](../history/evidence/project/406e1ef0da67e694_translation_review_report.json) · [report](../history/evidence/project/efe46be2b18d2502_step047_report.json) |
| STEP48 | 11 | 명시 없음/코드만 있음 | [report](../history/evidence/project/e11579942ccb9b9e_translation_review_report.json) · [report](../history/evidence/project/17f21f913c08f6d7_step048_report.json) |
| STEP49 | 11 | 명시 없음/코드만 있음 | [report](../history/evidence/project/9b08038734c0e316_translation_review_report.json) · [report](../history/evidence/project/d828ad8cc0742651_step049_report.json) |
| STEP50 | 11 | 명시 없음/코드만 있음 | [report](../history/evidence/project/ab55a5c5beb8c766_translation_review_report.json) · [report](../history/evidence/project/8c47762713b843be_step050_report.json) |
| STEP51 | 11 | 명시 없음/코드만 있음 | [report](../history/evidence/project/34c404e80b52d4a2_translation_review_report.json) · [report](../history/evidence/project/a93a59cca3f6326f_step051_report.json) |
| STEP52 | 11 | 명시 없음/코드만 있음 | [report](../history/evidence/project/e4719a404e226ddc_translation_review_report.json) · [report](../history/evidence/project/7bbe9f279596619f_step052_report.json) |
| STEP53 | 11 | 명시 없음/코드만 있음 | [report](../history/evidence/project/93fc7e5a64bb11e0_translation_review_report.json) · [report](../history/evidence/project/6efb349e7799d33e_step053_report.json) |
| STEP54 | 11 | 명시 없음/코드만 있음 | [report](../history/evidence/project/359d60995302983e_translation_review_report.json) · [report](../history/evidence/project/84c8f7853c6d2d22_step054_report.json) |
| STEP55 | 11 | 명시 없음/코드만 있음 | [report](../history/evidence/project/0ba185c3b249d922_translation_review_report.json) · [report](../history/evidence/project/ad5bef2bb583dab4_step055_report.json) |
| STEP56 | 11 | 명시 없음/코드만 있음 | [report](../history/evidence/project/075c9989bf04f527_translation_review_report.json) · [report](../history/evidence/project/2d2c7e3e888ccdf4_step056_report.json) |
| STEP57 | 11 | 명시 없음/코드만 있음 | [report](../history/evidence/project/7851cba3fa267607_translation_review_report.json) · [report](../history/evidence/project/946ccc98f5b1a1db_step057_report.json) |
| STEP58 | 10 | 명시 없음/코드만 있음 | [report](../history/evidence/project/d913765f3a610d79_translation_review_report.json) · [report](../history/evidence/project/d913765f3a610d79_translation_review_report.json) |
| STEP58 FIX1 | 11 | 명시 없음/코드만 있음 | [report](../history/evidence/project/7f4988b7d70b82f6_translation_review_report.json) · [report](../history/evidence/project/9dc17234d675f19f_step058_fix1_report.json) |
| STEP59 | 11 | 명시 없음/코드만 있음 | [report](../history/evidence/project/d0fdd11deb3c4faf_translation_review_report.json) · [report](../history/evidence/project/d45dbb41011a7418_step059_report.json) |
| STEP60 | 11 | 명시 없음/코드만 있음 | [report](../history/evidence/project/cb39231b0ab24e12_translation_review_report.json) · [report](../history/evidence/project/956347cabee5d9d7_step060_report.json) |
| STEP61 | 11 | 명시 없음/코드만 있음 | [report](../history/evidence/project/eba290ec17f078ab_translation_review_report.json) · [report](../history/evidence/project/66d2a2347e4dc5d4_step061_report.json) |
| STEP62 | 11 | 명시 없음/코드만 있음 | [report](../history/evidence/project/09a5c94a562e0569_translation_review_report.json) · [report](../history/evidence/project/57a6e98773db922c_step062_report.json) |
| STEP63 | 66 | status=VERIFIED | [report](../history/evidence/project/849de61430c774c2_step063_report.json) · [report](../history/evidence/project/ad3faea46cd35d33_stage07_report.json) |
| STEP64 | 63 | status=VERIFIED | [report](../history/evidence/project/202883f9ae264c86_step064_report.json) · [report](../history/evidence/project/573d2500ec0c9b22_stage40a_asset_inventory.json) |
| STEP65 | 9 | status=VERIFIED | [report](../history/evidence/project/89779ca06782f348_step065_report.json) · [note](../history/evidence/project/3cae07bd82bad675_PROJECT_STATE.md) |
| STEP66 | 9 | status=VERIFIED | [report](../history/evidence/project/bd75ebaf60516cfb_step066_report.json) · [note](../history/evidence/project/0e420f42f98f9abd_PROJECT_STATE.md) |
| STEP67 | 9 | status=VERIFIED | [report](../history/evidence/project/d69e697b1ba196f3_step067_report.json) · [note](../history/evidence/project/dd8d50990fb8516a_PROJECT_STATE.md) |
| STEP68 | 20 | 명시 없음/코드만 있음 | [report](../history/evidence/project/d2ea7d1182cc0d95_stage42a_report.json) · [report](../history/evidence/project/cfb88b323e71d75a_stage42d_build_report.json) |
| STEP68 FIX1 | 9 | status=VERIFIED | [report](../history/evidence/project/71db826992a8b726_step068_fix1_report.json) · [note](../history/evidence/project/0aeab0842225d901_PROJECT_STATE.md) |
| STEP69 | 10 | 명시 없음/코드만 있음 | [report](../history/evidence/project/ef8cae43b0a1fd35_int92_manifest.json) · [report](../history/evidence/project/ef8cae43b0a1fd35_int92_manifest.json) |
| STEP69 FIX1 | 10 | 명시 없음/코드만 있음 | [report](../history/evidence/project/ef8cae43b0a1fd35_int92_manifest.json) · [report](../history/evidence/project/ef8cae43b0a1fd35_int92_manifest.json) |
| STEP69 FIX2 | 11 | status=BUILT_UNVERIFIED; runtime_verified=False | [report](../history/evidence/project/ef8cae43b0a1fd35_int92_manifest.json) · [report](../history/evidence/project/aed5a426b30d86ab_step069_fix2_report.json) |
| STEP70 | 8 | 명시 없음/코드만 있음 | [note](../history/evidence/project/044f8b9f721aa84a_PROJECT_STATE.md) · [note](../history/evidence/project/5701385edfe40d6a_STEP_070.md) |
| STEP70 FIX1 | 10 | 명시 없음/코드만 있음 | [note](../history/evidence/project/6a45b0d69726bec5_PROJECT_STATE.md) · [note](../history/evidence/project/59b1bfc46a1f865e_STEP_070_FIX1.md) |
| STEP70 FIX2 | 10 | 명시 없음/코드만 있음 | [note](../history/evidence/project/2cfb84a72a9b5462_PROJECT_STATE.md) · [note](../history/evidence/project/11a328e7742c3bcc_STEP_070_FIX2.md) |
| STEP70 FIX3 | 9 | status=IN_PROGRESS; runtime_verified=False | [report](../history/evidence/project/e79dd4faa6bf2c47_step070_fix3_report.json) · [note](../history/evidence/project/913919a376a5dfb3_PROJECT_STATE.md) |
| STEP70 FIX4 | 9 | status=IN_PROGRESS; runtime_verified=False | [report](../history/evidence/project/9c8becf1c0c40ab2_step070_fix4_report.json) · [note](../history/evidence/project/9e16123c615bfd7e_PROJECT_STATE.md) |
| STEP70 FIX5 | 17 | status=IN_PROGRESS; runtime_verified=False | [report](../history/evidence/project/163303db936c7bcf_step070_fix5_report.json) · [report](../history/evidence/project/163303db936c7bcf_step070_fix5_report.json) |
| STEP70 FIX6 | 9 | status=RUNTIME_ROUTE_DISCOVERY_CAPTURED; runtime_verified=False | [report](../history/evidence/project/e2f640761f57b371_step070_fix6_report.json) · [note](../history/evidence/project/681486e9eaa2a3b6_PROJECT_STATE.md) |
| STEP70 FIX7 | 9 | status=MAIN_MENU_ROUTE_CAPTURED; runtime_verified=False | [report](../history/evidence/project/26ea469139cf06e7_step070_fix7_report.json) · [note](../history/evidence/project/df20739a7cd57b07_PROJECT_STATE.md) |
| STEP71 | 9 | status=SKIRMISH_ENTERED_INT92_RUNTIME_SCAN_COMPLETE; runtime_verified=False | [report](../history/evidence/project/86245ef9258d66c3_step071_report.json) · [note](../history/evidence/project/fcd581bfa8128393_PROJECT_STATE.md) |
| STEP71 FIX1 | 4 | 명시 없음/코드만 있음 | [source](../history/sources/project/59fc3b31d88ee0d8_run.ps1) · [source](../history/sources/project/d7de4349aa202a2c_step071_fix1.py) |
| STEP72 | 14 | status=BLOCKED_MISSING_EVIDENCE | [report](../history/evidence/project/4bc12e98f0b14e00_source_manifest.json) · [report](../history/evidence/project/bea7b0e97fb4b1c3_step072_report.json) |
| STEP72 FIX1 | 11 | status=VERIFIED_READY_FOR_GENERALIZED_PATCHER | [report](../history/evidence/project/537592d1677caa66_step072_fix1_report.json) · [note](../history/evidence/project/45a1255a34fe4480_PROJECT_STATE.md) |
| STEP73 | 16 | status=VERIFIED_SOURCE_RECOVERY | [report](../history/evidence/project/c2da7244d6eeec0a_source_recovery_manifest.json) · [report](../history/evidence/project/0c5d980a45520e71_step073_report.json) |
| STEP74 | 12 | status=BLOCKED_PREBUILD; runtime_verified=False | [report](../history/evidence/project/e31dad7469021707_step074_failed_report.json) · [note](../history/evidence/project/851b811282623cd9_PROJECT_STATE.md) |
| STEP74 FIX1 | 13 | status=BLOCKED_PREBUILD; runtime_verified=False | [report](../history/evidence/project/e31dad7469021707_step074_failed_report.json) · [report](../history/evidence/project/e31dad7469021707_step074_failed_report.json) |
| STEP74 FIX2 | 13 | status=BLOCKED_PREBUILD; runtime_verified=False | [report](../history/evidence/project/e31dad7469021707_step074_failed_report.json) · [report](../history/evidence/project/e31dad7469021707_step074_failed_report.json) |
| STEP74 FIX3 | 13 | status=BLOCKED_PREBUILD; runtime_verified=False | [report](../history/evidence/project/e31dad7469021707_step074_failed_report.json) · [report](../history/evidence/project/e31dad7469021707_step074_failed_report.json) |
| STEP74 FIX4 | 13 | status=BLOCKED_PREBUILD; runtime_verified=False | [report](../history/evidence/project/e31dad7469021707_step074_failed_report.json) · [report](../history/evidence/project/e31dad7469021707_step074_failed_report.json) |
| STEP74 FIX5 | 14 | status=BLOCKED_PREBUILD; runtime_verified=False | [report](../history/evidence/project/e31dad7469021707_step074_failed_report.json) · [report](../history/evidence/project/8efd90ee41ba96a6_step074_fix5_report.json) |
| STEP74 FIX6 | 14 | status=BLOCKED_PREBUILD; runtime_verified=False | [report](../history/evidence/project/e31dad7469021707_step074_failed_report.json) · [report](../history/evidence/project/2dd83e2432f6608f_step074_fix6_report.json) |
| STEP75 | 11 | status=VERIFIED_DSL_VARIANT_AUDIT | [report](../history/evidence/project/95d1f61c170ee1c9_step075_report.json) · [note](../history/evidence/project/b023d312d32e7049_PROJECT_STATE.md) |
| STEP76 | 12 | status=VERIFIED_DSL_VARIANT_AUDIT; status=VERIFIED_TARGETED_DSL_DIAGNOSTIC | [report](../history/evidence/project/95d1f61c170ee1c9_step075_report.json) · [report](../history/evidence/project/7af2399b2e9511c4_step076_report.json) |
| STEP77 | 13 | status=VERIFIED_TARGETED_DSL_DIAGNOSTIC; status=VERIFIED_PAYLOAD_CORRELATION_DIAGNOSTIC | [report](../history/evidence/project/7af2399b2e9511c4_step076_report.json) · [report](../history/evidence/project/d55075221bfedede_step077_report.json) |
| STEP78 | 13 | status=VERIFIED_BINARY_EVIDENCE_EXPORTED | [report](../history/evidence/project/438d559a54066f88_mdi_decoded_stream_inventory.json) · [report](../history/evidence/project/cf41b00f34a5e3dd_sample_manifest.json) |
| STEP79 | 14 | status=STRUCTURALLY_UNIQUE_NOT_RUNTIME_VERIFIED; status=BUILT_UNVERIFIED | [report](../history/evidence/project/512493ce5a965c22_dsl_binding_manifest.json) · [report](../history/evidence/project/3c9ebd554bb06eba_step079_report.json) |
| STEP80 | 14 | status=BUILT_UNVERIFIED; status=TITLE_MENU_VERIFIED_STORY_NOT_CONFIRMED; status=IN_PROGRESS | [report](../history/evidence/project/3c9ebd554bb06eba_step079_report.json) · [report](../history/evidence/project/cf9fa7cc888f88b7_step080_runtime_report.json) |
| STEP81 | 22 | status=BUILT_UNVERIFIED; status=IN_PROGRESS; status=NEW_GAME_NEXT_SCREEN_CAPTURED_VISUAL_REVIEW | [report](../history/evidence/project/3c9ebd554bb06eba_step079_report.json) · [report](../history/evidence/project/b001f53dce5ec148_step081_report_partial.json) |
| STEP82 | 14 | status=BUILT_UNVERIFIED; status=VERIFIED_BINARY_EVIDENCE_EXPORTED; status=IN_PROGRESS | [report](../history/evidence/project/3c9ebd554bb06eba_step079_report.json) · [report](../history/evidence/project/49f2c43c21ac5898_sample_manifest.json) |
| STEP83 | 20 | status=VERIFIED_BINARY_EVIDENCE_EXPORTED | [report](../history/evidence/project/2ff323d287a2848d_step082_report.json) · [report](../history/evidence/project/ccc39e88e18c35cf_test_memstick_manifest.json) |
| STEP83 FIX1 | 15 | status=VERIFIED_LIVE_SNAPSHOT_COLLECTED; status=VERIFIED_BINARY_EVIDENCE_EXPORTED | [report](../history/evidence/project/ed78ec608558a4bc_step083_live_font_report.json) · [report](../history/evidence/project/d6e5ac993a6ac4b2_test_memstick_manifest.json) |
| STEP84 | 6 | status=VERIFIED_OFFLINE_MEMORY_CONSISTENCY | [report](../history/evidence/project/3a9e4e5a213ba32c_step084_offline_report.json) · [note](../history/evidence/project/a03c73f3830c5d6c_PROJECT_STATE.md) |
| STEP85 | 7 | status=CAPTURE_COLLECTED_VISUAL_UNVERIFIED | [report](../history/evidence/project/ad7a8c0d2e2be8ad_step085_capture_report.json) · [note](../history/evidence/project/1fe72b48e9d48ac3_PROJECT_STATE.md) |
| STEP86 | 7 | status=WATCH_TRACE_COLLECTED_UNVERIFIED | [report](../history/evidence/project/59ca1369142048f8_step086_watch_report.json) · [note](../history/evidence/project/c11d76b2531a5f88_PROJECT_STATE.md) |
| STEP87 | 4 | status=COMPLETE_OFFLINE_DIAGNOSTIC_CLEANUP | [report](../history/evidence/project/b137195876e65254_step087_report.json) · [note](../history/evidence/project/17c3924cc65ea949_PROJECT_STATE.md) |
| STEP88 | 23 | status=FAILED; error=UNEXPECTED_CPU_PAUSE | [report](../history/evidence/project/837baa49167759e3_step088_register_report.json) · [note](../history/evidence/project/7bf07f59459f191a_PROJECT_STATE.md) |
| STEP88 FIX1 | 1 | 명시 없음/코드만 있음 | [note](../history/evidence/project/62b55a4a5bfd402b_STEP_088_FIX1.md) |
| STEP89 | 1 | 명시 없음/코드만 있음 | [note](../history/evidence/project/abe66375d8c734f8_STEP_089.md) |
| STEP90 | 1 | 명시 없음/코드만 있음 | [note](../history/evidence/project/c4419801ccdd71f9_STEP_090.md) |
| STEP91 | 1 | 명시 없음/코드만 있음 | [note](../history/evidence/project/7c41495a00d4e2d8_STEP_091.md) |
| STEP92 | 1 | 명시 없음/코드만 있음 | [note](../history/evidence/project/b0fc774751b0b590_STEP_092.md) |
| STEP93 | 1 | 명시 없음/코드만 있음 | [note](../history/evidence/project/bdac3081dca8093b_STEP_093.md) |
| STEP94 | 1 | 명시 없음/코드만 있음 | [note](../history/evidence/project/32f4bfeb3d6264ab_STEP_094.md) |
| STEP95 | 10 | 명시 없음/코드만 있음 | [source](../history/sources/project/4a325304b39ee8bd_capture_owner_init.py) · [source](../history/sources/project/54aa6b2ab3c9d145_capture_unicode_font.py) |
| STEP95 FIX1 | 9 | 명시 없음/코드만 있음 | [note](../history/evidence/project/31ec68d6d776892b_STEP_095_FIX1.md) · [source](../history/sources/project/1799b72989132cfb_LAUNCH.ps1) |
| STEP95 FIX2 | 38 | status=ARMED_PASSIVE | [report](../history/evidence/project/ab8fc391d1710964_VALIDATION_RESULTS.json) · [report](../history/evidence/project/ab8fc391d1710964_VALIDATION_RESULTS.json) |
| STEP95 FIX3 | 6 | success=False | [report](../history/evidence/project/0409e9afd9f47843_SUPERVISOR_RESULT.json) · [source](../history/sources/project/b9eceea93220976b_LAUNCH.ps1) |
| STEP96 | 1 | success=True | [report](../history/evidence/project/48929ce0fce45218_SUPERVISOR_RESULT.json) |
| STEP097 | 5 | 명시 없음/코드만 있음 | [source](../history/sources/session-work/59241f9d3109253a_build097_ufont.py) · [source](../history/sources/session-work/59012973d8ee873a_prep097_runtime.py) |
| STEP97 | 3 | runtime_verified=True | [report](../history/evidence/session-outputs/9f5d5ed7103146cb_build_report.json) · [report](../history/evidence/session-outputs/8b578491441ee857_live_font_verification.json) |
| STEP098 | 3 | 명시 없음/코드만 있음 | [source](../history/sources/session-work/845303e054908b8c_build098_all_ufonts.py) · [source](../history/sources/session-work/1a06aa8dc0018607_prep098_runtime.py) |
| STEP98 | 3 | 명시 없음/코드만 있음 | [report](../history/evidence/session-outputs/c0aae37f2a0ebaca_build_report.json) · [report](../history/evidence/session-outputs/50aa14e90dfe4782_inventory.json) |
| STEP099 | 3 | 명시 없음/코드만 있음 | [source](../history/sources/session-work/3229ee7d65303948_audit099_completion.py) · [source](../history/sources/session-work/28b9dffb8da74e89_build099_completion.py) |
| STEP99 | 1 | 명시 없음/코드만 있음 | [report](../history/evidence/session-outputs/1d8fdad466bbc178_build_report.json) |
| STEP100 | 4 | status=UNRESOLVED_REQUIRES_ENDING_SCENE_CAPTURE | [report](../history/evidence/session-outputs/0fd8e5f3f8bb072d_game_status.json) · [report](../history/evidence/session-outputs/bdaf553cd06e0449_issue_report.json) |
| STEP101 | 4 | 명시 없음/코드만 있음 | [report](../history/evidence/session-outputs/29999324a3a4534e_build_report.json) · [source](../history/sources/session-work/a0d9217cbc01381e_audit101_loading.py) |
| STEP102 | 4 | 명시 없음/코드만 있음 | [report](../history/evidence/session-outputs/0b760b1c3c43b316_build_report.json) · [source](../history/sources/session-work/6e73aca04730de9b_audit102_failed.py) |
| STEP103 | 4 | 명시 없음/코드만 있음 | [report](../history/evidence/session-outputs/fa561d60e755aa65_build_report.json) · [source](../history/sources/session-work/d69d52398b5690a3_audit103_confirm.py) |
| STEP104 | 7 | runtime_verified=True | [report](../history/evidence/session-outputs/c344f5ffe9d5749e_latest_status.json) · [report](../history/evidence/session-outputs/b94463a9af7d02d2_native_read_report.json) |
| STEP105 | 5 | 명시 없음/코드만 있음 | [report](../history/evidence/session-outputs/7b60f7e290a7eb2d_build_report.json) · [source](../history/sources/session-work/2abb785bdb711d7e_audit105_pickup.py) |
| STEP106 | 4 | runtime_verified=False | [report](../history/evidence/session-outputs/fdade193757255fd_build_report.json) · [report](../history/evidence/session-outputs/ec4bd490b5774598_native_read_report.json) |
| STEP107 | 4 | 명시 없음/코드만 있음 | [report](../history/evidence/session-outputs/471a92b40905e671_build_report.json) · [source](../history/sources/session-work/0541d94cf8a22eef_audit107_location.py) |
| STEP108 | 4 | 명시 없음/코드만 있음 | [report](../history/evidence/session-outputs/df6f68bcf71eb756_build_report.json) · [source](../history/sources/session-work/11394d3a486112a5_audit108_carentan.py) |
| STEP109 | 6 | 명시 없음/코드만 있음 | [report](../history/evidence/session-outputs/8770e7d2c790ce60_build_report.json) · [report](../history/evidence/session-outputs/e570e8494f88cee0_levelinfo_inventory.json) |
| STEP110 | 4 | 명시 없음/코드만 있음 | [report](../history/evidence/session-outputs/e96ff3255ea2b1a8_build_report.json) · [source](../history/sources/session-work/1e3b6cecbfca7be3_audit110_pause.py) |
| STEP111 | 6 | 명시 없음/코드만 있음 | [report](../history/evidence/session-outputs/a719b6fa24168c45_build_report.json) · [report](../history/evidence/session-outputs/1b5f56c8c4d6ca9b_repack_inventory.json) |
| STEP112 | 12 | 명시 없음/코드만 있음 | [report](../history/evidence/session-outputs/911b60073b1b0170_build_report.json) · [report](../history/evidence/session-outputs/c86450a53a922332_interaction_build_report.json) |
| STEP113 | 1 | 명시 없음/코드만 있음 | [report](../history/evidence/session-outputs/f60d5ea50dbb2a87_native_read_report.json) |
| STEP114 | 8 | 명시 없음/코드만 있음 | [report](../history/evidence/session-outputs/6994491acc8c1470_build_report.json) · [report](../history/evidence/session-outputs/2da15e3c51df5b4c_native_read_report.json) |
| STEP115 | 3 | 명시 없음/코드만 있음 | [report](../history/evidence/session-outputs/ac5f0af518639dd7_build_report.json) · [report](../history/evidence/session-outputs/ac28009b3d71832a_native_read_report.json) |
| STEP116 | 6 | 명시 없음/코드만 있음 | [report](../history/evidence/session-outputs/c4eb8360a79766c8_build_report.json) · [source](../history/sources/session-work/109fe87ea681d971_audit116.py) |
| STEP117 | 8 | 명시 없음/코드만 있음 | [report](../history/evidence/session-outputs/5e8d5acd8037cd0c_build_report.json) · [report](../history/evidence/session-outputs/f315f5e4c0a0f706_current_gpu_summary.json) |
| STEP118 | 4 | 명시 없음/코드만 있음 | [report](../history/evidence/session-outputs/93a9312b3f3865c2_build_report.json) · [report](../history/evidence/session-outputs/ac28009b3d71832a_native_read_report.json) |
| STEP119 | 7 | 명시 없음/코드만 있음 | [report](../history/evidence/session-outputs/2cffd5a3d1692427_build_report.json) · [source](../history/sources/session-work/9b6e14a24e14b7bc_audit119.py) |
| STEP120 | 5 | 명시 없음/코드만 있음 | [report](../history/evidence/session-outputs/0baaa6b35eaab99e_build_report.json) · [source](../history/sources/session-work/69240f50b4a265a6_audit120.py) |
| STEP121 | 3 | 명시 없음/코드만 있음 | [report](../history/evidence/session-outputs/ac28009b3d71832a_native_read_report.json) · [source](../history/sources/session-work/f954fbf305eab4e2_prep121.py) |
| STEP123 | 13 | 명시 없음/코드만 있음 | [report](../history/evidence/session-outputs/d0c545b2512c3033_build_report.json) · [report](../history/evidence/session-outputs/3f50da49073fca30_font_hash_verification.json) |
| STEP124 | 10 | 명시 없음/코드만 있음 | [report](../history/evidence/session-outputs/5f71cbdc594090f6_build_report.json) · [source](../history/sources/session-work/7e9e7c2afd0dd9cf_audit124.py) |
| STEP125 | 3 | status=BUILT_UNVERIFIED; runtime_verified=False | [report](../history/evidence/project/922ee850ab418cb4_build_report.json) · [note](../history/evidence/project/736a70c436423541_RESULT.txt) |
| STEP126 | 2 | 명시 없음/코드만 있음 | [note](../history/evidence/project/c845d12857201c5e_RESULT.txt) · [source](../history/sources/project/9dcfbcc8e3e8d55d_step126_rank_fix.py) |
| STEP127 FIX1 | 2 | status=BUILT_UNVERIFIED; runtime_verified=False | [report](../history/evidence/project/fbf0b2f59206678c_build_report.json) · [note](../history/evidence/project/58a00d9eb557bbca_RESULT.txt) |
| STEP128 | 3 | status=BUILT_UNVERIFIED; runtime_verified=False | [report](../history/evidence/project/d4eb79235f5703f9_build_report.json) · [report](../history/evidence/project/0730f3599f4cc49d_candidate_inventory.json) |

## 보존 범위와 공백

원본/결과 ISO, 추출 게임 자산, 영상·음원·이미지, 세이브, 개인 실행 로그, 인증정보, 외부 패키지는 포함하지 않았다. 큰 보고서(2MB 초과)는 제외 목록에 남겼다. JSON의 긴 필드·큰 배열·민감 필드는 삭제/축약될 수 있다. 전체 대화 원문은 이번 범위가 아니다.

동일 내용의 중복 파일은 공개본 하나로 연결했다. ALREADY_PRESENT는 이미 저장소에 같은 정규화 내용이 있다는 뜻이고, DUPLICATE_ARCHIVED는 이번 보관본을 공유한다는 뜻이다. 어느 쪽도 실행 성공을 뜻하지 않는다.

심볼릭 링크/재분석 지점은 따라가지 않았고 중첩 깊이 제한이 있다. 디스크 전체 작업의 완전한 보존을 주장하지 않는다. 확인하지 못했거나 제외한 항목은 HISTORY_INVENTORY.json의 disposition과 scope warnings를 확인한다.

검사: `python tools/check_history.py`. 이 검사는 인덱스와 공개본의 무결성만 검사한다.

외부 라이브러리/참조 소스는 별도 제외했다. 원래 배포처와 라이선스를 확인해 설치하며 프로젝트 자체 개발 코드로 재배포하지 않는다.
