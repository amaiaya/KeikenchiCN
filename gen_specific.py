from gen_vis_keikenchi_map import read_base_border_csvs, read_points_csv, visualize_with_points, load_path_data

border_type = 'wgs'
path_type = border_type
date_label = '20261009'

read_list = [
    f'border_data/mainland/china_mainland_boundaries_{border_type}.csv',
    f'border_data/hong_kong/hk_boundaries_{border_type}.csv',
    f'border_data/macau/mc_boundaries_{border_type}.csv',
    # f'border_data/taiwan/taiwan_town_boundaries_{border_type}.csv',
    # f'border_data/japan/japan_boundaries_{border_type}.csv',
]
border_data = read_base_border_csvs(read_list)
label_json=f'add_labels/add_label_list_fullname_{date_label}.json'
_, path_data = load_path_data(date=date_label)
# visualize_with_points(border_data, points_df=path_data, show_points=True, fig_width=100, format='jpg', label_json=label_json, target_names=['广东省', '广西壮族自治区', '香港特別行政區', '澳門特別行政區'])
visualize_with_points(border_data, points_df=path_data, show_points=True, fig_width=100, format='jpg', label_json=label_json, target_names=['珠海市', '香港特別行政區', '澳門特別行政區'])
