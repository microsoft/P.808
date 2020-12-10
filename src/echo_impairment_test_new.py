import math
import random
import os
import jinja2
import numpy as np
import pandas as pd


def create_input_for_echo_impairment(cfg, df, output_path):
    """
    create the input for the acr methods
    :param cfg:
    :param df:
    :param output_path:
    :return:
    """
    mixed_clips = df['rating_clips_mixed'].dropna()
    model_clips = df['rating_clips_model'].dropna()
    n_clips = mixed_clips.count()
    n_sessions = math.ceil(n_clips / int(cfg['number_of_clips_per_session']))

    print(f'{n_clips} clips and {n_sessions} sessions')

    # create math
    math_source = df['math'].dropna()
    math_output = np.tile(math_source.to_numpy(),
                          (n_sessions // math_source.count()) + 1)[:n_sessions]

    # CMPs: 4 pairs are needed for 1 session
    nPairs = 4 * n_sessions
    pair_a = df['pair_a'].dropna()
    pair_b = df['pair_b'].dropna()
    pair_a_extended = np.tile(
        pair_a.to_numpy(), (nPairs // pair_a.count()) + 1)[:nPairs]
    pair_b_extended = np.tile(
        pair_b.to_numpy(), (nPairs // pair_b.count()) + 1)[:nPairs]

    # randomly select pairs and swap a and b
    swap_me = np.random.randint(2, size=nPairs)
    tmp = np.copy(pair_a_extended)
    pair_a_extended[swap_me == 1] = pair_b_extended[swap_me == 1]
    pair_b_extended[swap_me == 1] = tmp[swap_me == 1]

    full_array = np.transpose(np.array([pair_a_extended, pair_b_extended]))
    new_4 = np.reshape(full_array, (n_sessions, 8))
    for i in range(n_sessions):
        new_4[i] = np.roll(new_4[i], random.randint(1, 3) * 2)

    output_df = pd.DataFrame({'CMP1_A': new_4[:, 0], 'CMP1_B': new_4[:, 1],
                              'CMP2_A': new_4[:, 2], 'CMP2_B': new_4[:, 3],
                              'CMP3_A': new_4[:, 4], 'CMP3_B': new_4[:, 5],
                              'CMP4_A': new_4[:, 6], 'CMP4_B': new_4[:, 7]})

    # add math
    output_df['math'] = math_output
    # rating_clips
    #   repeat some clips to have a full design
    n_questions = int(cfg['number_of_clips_per_session'])
    needed_clips = n_sessions * n_questions
    full_mixed = np.tile(mixed_clips.to_numpy(),
                         (needed_clips // n_clips) + 1)[:needed_clips]
    full_model = np.tile(model_clips.to_numpy(),
                         (needed_clips // n_clips) + 1)[:needed_clips]
    #   check the method: clips_selection_strategy
    full = list(zip(full_mixed, full_model))
    random.shuffle(full)
    full_mixed, full_model = zip(*full)

    mixed_clips_sessions = np.reshape(full_mixed, (n_sessions, n_questions))
    model_clips_sessions = np.reshape(full_model, (n_sessions, n_questions))

    for q in range(n_questions):
        output_df[f'Q{q}_mixed'] = mixed_clips_sessions[:, q]
        output_df[f'Q{q}_model'] = model_clips_sessions[:, q]

    # trappings
    if int(cfg['number_of_trapping_per_session']) > 0:
        if int(cfg['number_of_trapping_per_session']) > 1:
            print("more than one TP is not supported for now - continue with 1")
        # n_trappings = int(cfg['general']['number_of_trapping_per_session']) * n_sessions
        n_trappings = n_sessions
        trap_source = df['trapping_clips'].dropna()
        trap_ans_source = df['trapping_ans'].dropna()

        full_trappings = np.tile(trap_source.to_numpy(
        ), (n_trappings // trap_source.count()) + 1)[:n_trappings]
        full_trappings_answer = np.tile(trap_ans_source.to_numpy(), (n_trappings // trap_ans_source.count()) + 1)[
            :n_trappings]

        full_tp = list(zip(full_trappings, full_trappings_answer))
        random.shuffle(full_tp)

        full_trappings, full_trappings_answer = zip(*full_tp)
        output_df['TP'] = full_trappings
        output_df['TP_ANS'] = full_trappings_answer
    # gold_clips
    if int(cfg['number_of_gold_clips_per_session']) > 0:
        if int(cfg['number_of_gold_clips_per_session']) > 1:
            print("more than one gold_clip is not supported for now - continue with 1")
        n_gold_clips = n_sessions

        gold_clips_mixed_source, gold_clips_mixed_ans = df['gold_clips_mixed'].dropna(), df['gold_clips_mixed_ans'].dropna()
        gold_clips_model_source, gold_clips_model_ans = df['gold_clips_model'].dropna(), df['gold_clips_model_ans'].dropna()

        full_gold_clips_mixed = _tile_gold_clips(gold_clips_mixed_source, n_gold_clips)
        full_gold_clips_mixed_ans = _tile_gold_clips(gold_clips_mixed_ans, n_gold_clips)
        full_gold_clips_model = _tile_gold_clips(gold_clips_model_source, n_gold_clips)
        full_gold_clips_model_ans = _tile_gold_clips(gold_clips_model_ans, n_gold_clips)

        full_gc = list(zip(full_gold_clips_mixed, full_gold_clips_mixed_ans,
                           full_gold_clips_model, full_gold_clips_model_ans))
        random.shuffle(full_gc)

        full_gold_clips_mixed, full_gold_clips_mixed_ans, full_gold_clips_model, full_gold_clips_model_ans = zip(
            *full_gc)
        output_df['gold_clips_mixed'] = full_gold_clips_mixed
        output_df['gold_clips_mixed_ans'] = full_gold_clips_mixed_ans
        output_df['gold_clips_model'] = full_gold_clips_model
        output_df['gold_clips_model_ans'] = full_gold_clips_model_ans

    output_df.to_csv(output_path, index=False)
    return len(output_df)


def create_hit_app_echo_impairment_new(cfg, template_path, training_path, trap_path, cfg_g, cfg_trapping_store, general_cfg):
    """Create the echo_impairment_test_new.html file corresponding to this project"""

    print("Start creating custom echo_impairment_test_new.html")
    df_trap = pd.DataFrame()
    if trap_path and os.path.exists(trap_path):
        df_trap = pd.read_csv(trap_path, nrows=1)
    else:
        raise NotImplementedError(
            'Azure storage based trapping clips are not support for this HIT yet')

    # trapping clips are required, at list 1 clip should be available here
    if len(df_trap.index) < 1 and int(cfg_g['number_of_clips_per_session']) > 0:
        raise (f"At least one trapping clip is required")
    for _, row in df_trap.head(n=1).iterrows():
        trap_url = row['trapping_clips']
        trap_ans = row['trapping_ans']

    config = {}
    config['cookie_name'] = cfg['cookie_name']
    config['qual_cookie_name'] = cfg['qual_cookie_name']
    config['allowed_max_hit_in_project'] = cfg['allowed_max_hit_in_project']
    config['training_trap_urls'] = trap_url
    config['training_trap_ans'] = trap_ans
    config['contact_email'] = cfg["contact_email"]

    config['hit_base_payment'] = cfg['hit_base_payment']
    config['quantity_hits_more_than'] = cfg['quantity_hits_more_than']
    config['quantity_bonus'] = cfg['quantity_bonus']
    config['quality_top_percentage'] = cfg['quality_top_percentage']
    config['quality_bonus'] = float(
        cfg['quality_bonus']) + float(cfg['quantity_bonus'])
    config['sum_quantity'] = float(
        cfg['quantity_bonus']) + float(cfg['hit_base_payment'])
    config['sum_quality'] = config['quality_bonus'] + \
        float(cfg['hit_base_payment'])
    config = {**config, **general_cfg}

    df_train = pd.read_csv(training_path)
    train = []
    for _, row in df_train.iterrows():
        train.append({'mixed': row['training_clips_mixed'],
                      'model': row['training_clips_model'], 'dummy': 'dummy'})
    train.append({'mixed': trap_url, 'model': trap_url, 'dummy': 'dummy'})
    config['training_urls'] = train

    # rating urls
    rating_urls = []
    n_clips = int(cfg_g['number_of_clips_per_session'])
    n_traps = int(cfg_g['number_of_trapping_per_session'])
    n_gold_clips = int(cfg_g['number_of_gold_clips_per_session'])

    for i in range(0, n_clips):
        rating_urls.append({'mixed': f'${{Q{i}_mixed}}',
                            'model': f'${{Q{i}_model}}', 'dummy': 'dummy'})

    if n_traps > 1:
        raise Exception(
            "more than 1 trapping clips question is not supported.")
    elif n_traps == 1:
        rating_urls.append(
            {'mixed': '${TP}', 'model': '${TP}', 'dummy': 'dummy'})

    if n_gold_clips > 1:
        raise Exception("more than 1 gold question is not supported.")
    elif n_gold_clips == 1:
        rating_urls.append(
            {'mixed': '${gold_clip_mixed}', 'model': '${gold_clip_model}', 'dummy': 'dummy'})

    config['rating_urls'] = rating_urls

    with open(template_path, 'r') as f:
        content = f.read()
    template = jinja2.Template(content)
    return template.render(cfg=config)


def _tile_gold_clips(clips_series, num_gold_clips):
    tile_count = (num_gold_clips // clips_series.count()) + 1
    return np.tile(clips_series.to_numpy(), tile_count)[:num_gold_clips]
