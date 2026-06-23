from gen_vis_keikenchi_map import read_base_border_csvs, read_points_csv, visualize_with_points

border_type = 'wgs'
path_type = border_type

# # KZ
# read_list = ['border_data/GeoBoundaries/KAZ/KAZ_ADM2_boundaries_wgs.csv']
# read_list = ['border_data/OSM/Kazakhstan_boundaries_wgs.csv']
# border_data = read_base_border_csvs(read_list)
# path_data = read_points_csv(f'fwss_reader/loca_20260614_{path_type}.csv')
# label_json='add_labels/add_label_list_fullname.json'
# visualize_with_points(border_data, path_data, show_points=False, fig_width=50, format='jpg', prefix_name='test_figs/kz_osm')

# # Turkmenistan
# read_list = ['border_data/OSM/Turkmenistan_boundaries_wgs.csv']
# border_data = read_base_border_csvs(read_list)
# path_data = read_points_csv(f'fwss_reader/loca_20260614_{path_type}.csv')
# label_json='add_labels/add_label_list_fullname.json'
# visualize_with_points(border_data, path_data, show_points=False, fig_width=50, format='jpg', prefix_name='test_figs/Turkmenistan_osm')

# # Central Asia
# read_list = ['border_data/OSM/Kazakhstan_boundaries_wgs.csv',
#              'border_data/OSM/Tajikistan_boundaries_wgs.csv',
#              'border_data/OSM/Uzbekistan_boundaries_wgs.csv',
#              'border_data/GeoBoundaries/KGZ/KGZ_ADM2_boundaries_wgs.csv',
#              'border_data/GeoBoundaries/TKM/TKM_ADM2_boundaries_wgs.csv',]
# border_data = read_base_border_csvs(read_list)
# path_data = read_points_csv(f'fwss_reader/loca_20260614_{path_type}.csv')
# label_json='add_labels/add_label_list_fullname.json'
# visualize_with_points(border_data, path_data, show_points=False, fig_width=100, format='jpg', prefix_name='test_figs/central_asia')

# Asia
read_list = ['border_data/OSM/Kazakhstan_boundaries_wgs.csv',
             'border_data/OSM/Tajikistan_boundaries_wgs.csv',
             'border_data/OSM/Uzbekistan_boundaries_wgs.csv',
             'border_data/GeoBoundaries/KGZ/KGZ_ADM2_boundaries_wgs.csv',
             'border_data/GeoBoundaries/TKM/TKM_ADM2_boundaries_wgs.csv',
             'border_data/GeoBoundaries/RUS/RUS_ADM2_boundaries_wgs.csv',
            f'border_data/mainland/china_mainland_boundaries_{border_type}.csv',
            f'border_data/hong_kong/hk_boundaries_{border_type}.csv',
            f'border_data/macau/mc_boundaries_{border_type}.csv',
            f'border_data/taiwan/taiwan_town_boundaries_{border_type}.csv',
            f'border_data/japan/japan_boundaries_{border_type}.csv',
            f'border_data/vietnam/vn_1_boundaries_{border_type}.csv',
            f'border_data/south_korea/sk_boundaries_{border_type}.csv',
            f'border_data/north_korea/nk_boundaries_{border_type}.csv',
            f'border_data/GeoBoundaries/MNG/MNG_ADM2_boundaries_{border_type}.csv',]
border_data = read_base_border_csvs(read_list)
label_json='add_labels/add_label_list_fullname.json'
visualize_with_points(border_data, points_df=None, show_points=False, fig_width=100, format='jpg', prefix_name='test_figs/asia_m')

# Russia
# read_list = [
#              'border_data/GeoBoundaries/RUS/RUS_ADM0_boundaries_wgs.csv',
#             #  'border_data/GeoBoundaries/TKM/TKM_ADM2_boundaries_wgs.csv',
#              ]
# border_data = read_base_border_csvs(read_list)
# label_json='add_labels/add_label_list_fullname.json'
# visualize_with_points(border_data, points_df=None, show_points=False, fig_width=100, format='jpg', prefix_name='test_figs/russia')