function Run-FinalOosPanel {
  py -3.14 research\final_oos_panel.py `
    --development-tasks results\development_panel_aud_usd_gbp_chf\development_panel_tasks.csv `
    --development-summary results\development_panel_aud_usd_gbp_chf\development_panel_summary.csv `
    --config config.toml `
    --target AUD_USD `
    --ref GBP_CHF `
    --output-dir results\final_oos_panel_aud_usd_gbp_chf
}

function Run-DevelopmentPanel {
  py -3.14 research\development_panel.py `
    --tasks results\signal_consensus\signal_consensus_tasks.csv `
    --config config.toml `
    --target CAD_JPY `
    --ref GBP_CHF `
    --output-dir results\development_panel_cad_jpy_gbp_chf
}

function Run-PrePanel {
  py -3.14 research\hold_response.py --ranking ranking_result\trade_ranking_full.csv --output-dir results\hold_response

  py -3.14 research\hold_response.py --ranking ranking_result\trade_ranking_streak_breakout_full.csv --output-dir results\hold_response_streak_breakout

  py -3.14 research\signal_consensus.py `
    --hold-response `
      results\hold_response\hold_response_series.csv `
      results\hold_response_streak_breakout\hold_response_series.csv `
    --output-dir results\signal_consensus
}

function main {
  Run-DevelopmentPanel
}

main