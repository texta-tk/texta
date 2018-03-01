from collections import Counter, defaultdict
import re
import math


class Highlighter(object):

    def __init__(self, average_colors=False, derive_spans=False, derived_span_string='"', default_category='[match]',
                additional_style_string=''):
        """
        Parameters:
            average_colors: boolean
                If True, color codes of the overlapping highlights are averaged.
                If False, the most common color code for the overlapping highlights is selected.

            derive_spans: boolean
                If True, Highlighter will try to derive further highlight_data from the existing tagged_text.
                Expects highlights to be represented as spans.
                If False, Highlighter wont try to derive highlight_data.

            default_category: string
                If derive_spans == True and derived highlight_data misses class attribute to use as a category,
                its category will be set to default_dategory.
        """

        self._average_colors = average_colors
        self._derive_spans = derive_spans
        self._derived_span_string = derived_span_string

        self._class_pattern = re.compile(r'class\s*=\s*"(.*)"')
        self._color_pattern = re.compile(r'style\s*=\s*"background-color:\s*(\S*)\s*;?"')

        self._default_category = default_category

        self._additional_style_string = additional_style_string

    def highlight(self, original_text, highlight_data, tagged_text=None):
        """highlight_data = [{'spans': [[1,7],[25,36]], 'name': 'LOC', 'value': '5', 'category': '[fact]', 'color': '#ababab'}]
        """
        if tagged_text:
            if self._derive_spans:
                alignment = [char_idx for char_idx in range(len(original_text))]
                highlight_data.extend(self._derive_highlight_data(tagged_text))
                tagged_text = original_text
            else:
                alignment = self._align_texts(original_text, tagged_text)
        else:
            alignment = [char_idx for char_idx in range(len(original_text))]
            tagged_text = original_text

        spans_to_tags = self._get_tags_for_text_index(tagged_text, alignment, highlight_data)
        split_text = self._split_text_at_indices(tagged_text, [index for span, tag in spans_to_tags for index in span])

        return self._merge_text_and_tags(split_text, [tag for span, tag in spans_to_tags])

    def _merge_text_and_tags(self, split_text, start_tags):
        insert_start_tag = True
        start_tags_idx = 0
        final_text = []

        for text_part in split_text[:-1]:
            final_text.append(text_part)
            if insert_start_tag:
                final_text.append(start_tags[start_tags_idx])
                start_tags_idx += 1
            else:
                final_text.append('</span>')
            insert_start_tag = not insert_start_tag

        final_text.append(split_text[-1])

        return ''.join(final_text)

    def _derive_highlight_data(self, tagged_text):
        highlight_data = []
        span_end = 0
        start_tag_index = tagged_text.find('<span', span_end)
        index_discount = 0

        while start_tag_index > 0:
            start_tag_end = tagged_text.find('>', start_tag_index + 5) + 1
            span_end = tagged_text.find('</span>', start_tag_end)

            index_discount += start_tag_end - start_tag_index

            span_data = self._extract_span_data(tagged_text[start_tag_index + 5:start_tag_end - 1].strip(),
                                                [[start_tag_end - index_discount, span_end - index_discount]])
            if span_data:
                highlight_data.append(span_data)

            start_tag_index = tagged_text.find('<span', span_end + 7)
            index_discount += 7

        return highlight_data

    def _extract_span_data(self, span_attributes_string, spans):
        span_data = {}

        for match_name, match_pattern in [('category', self._class_pattern), ('color', self._color_pattern)]:
            match = match_pattern.search(span_attributes_string)

            if match:
                span_data[match_name] = match.groups(0)[0]
            elif match_name == 'category':
                span_data[match_name] = self._default_category

            span_data['spans'] = spans

        return span_data

    def _align_texts(self, original_text, tagged_text):
        alignment = []

        tagged_text_idx = 0
        for char in original_text:
            while tagged_text[tagged_text_idx] == '<':
                while tagged_text[tagged_text_idx] != '>':
                    tagged_text_idx += 1
                tagged_text_idx += 1

            if char == tagged_text[tagged_text_idx]:
                alignment.append(tagged_text_idx)

            tagged_text_idx += 1

        return alignment

    def _split_text_at_indices(self, text, indices):
        slice_start_idx = 0
        text_slices = []

        for index in indices:
            text_slices.append(text[slice_start_idx:index])
            slice_start_idx = index

        text_slices.append(text[slice_start_idx:])

        return text_slices

    def _get_tags_for_text_index(self, text, alignment, highlight_data):
        data_mapping = {index: datum for index, datum in enumerate(highlight_data)}
        data_index_to_spans = [datum['spans'] for datum in highlight_data]

        text_index_to_data_index = [[] for i in range(len(text))]
        for data_index, spans in enumerate(data_index_to_spans):
            for span in spans:
                for text_index in range(*span):
                    text_index_to_data_index[alignment[text_index]].append(data_index)

        text_index_to_data_index = [frozenset(data_indices) for data_indices in text_index_to_data_index]

        spans_to_tags = [(spans, self._get_tag_from_highlight_data([data_mapping[data_index] for data_index in data_indices]))
                         for spans, data_indices in self._get_spans_to_data_indices(text_index_to_data_index)]

        return spans_to_tags

    def _get_spans_to_data_indices(self, text_index_to_data_index):
        spans_to_data_indices = []
        start_idx = 0

        if text_index_to_data_index:
            previous_data_indices = text_index_to_data_index[0]
            text_idx = None

            for text_idx, data_indices in enumerate(text_index_to_data_index):
                if data_indices == previous_data_indices:
                    continue

                spans_to_data_indices.append(([start_idx, text_idx], previous_data_indices))
                previous_data_indices = data_indices
                start_idx = text_idx

            if text_idx is not None:
                spans_to_data_indices.append(([start_idx, text_idx + 1], previous_data_indices))

        return spans_to_data_indices

    def _get_tag_from_highlight_data(self, highlight_data_list):
        category_name_value = defaultdict(lambda: defaultdict(list))
        for highlight_data in highlight_data_list:
            category = highlight_data.get('category', self._default_category)
            name = highlight_data.get('name', '')
            value = highlight_data.get('value', None)

            # Creating category_name_value[category][name] = [].
            # Important for cases when value is missing.
            category_name_value[category][name]

            if value:
                category_name_value[category][name].append(value)

        title_lines = []
        for category in category_name_value:
            title_line_tokens = [category]
            for name in category_name_value[category]:
                if category_name_value[category][name]:
                    for value in category_name_value[category][name]:
                        title_line_tokens.append('%s=%s'%(name, value))
                else:
                    title_line_tokens.append(name)
            title_lines.append(' '.join(title_line_tokens))

        title = ('&#13;'.join(title_lines))
        color = self._get_color([highlight_data['color'] for highlight_data in highlight_data_list if 'color' in highlight_data])

        if '[fact]' in title or '[fact_val]' in title or '[ES]' in title:
            return u'<span class="[HL]" title="{0}" style="background-color: {1};{2}">'.format(
            title, color, (self._additional_style_string if color != 'none' else ''))

        return u'<span title="{0}" style="background-color: {1};{2}">'.format(
            title, color, (self._additional_style_string if color != 'none' else ''))

    def _get_color(self, color_code_list):
        if not color_code_list:
            return 'none'
        if self._average_colors:
            red, green, blue = 0, 0, 0

            for color_code in color_code_list:
                r, g, b = int(color_code[1:3], 16), int(color_code[3:5], 16), int(color_code[5:], 16)
                red += r
                green += g
                blue += b

            red = int(red/len(color_code_list))
            green = int(green/len(color_code_list))
            blue = int(blue/len(color_code_list))

            return "#%02x%02x%02x"%(red, green, blue)
        else:
            return Counter(color_code_list).most_common(1)[0][0]


class ColorPicker(object):

    colors = ["#E69F00", "#56B4E9", "#009E73", "#F0E442", "#0072B2", "#D55E00", "#CC79A7", "#999999"]

    @staticmethod
    def get_color_map(keys, colors=None):
        keys = list(keys)
        colors = colors if colors else ColorPicker.colors

        # Wrap colors if there are more keys needing colors than colors themselves.
        colors = colors * int(math.ceil(float(len(keys)) / len(colors)))

        return {key: colors[key_idx] for key_idx, key in enumerate(keys)}


if __name__ == '__main__':
    hl = Highlighter(average_colors=True, derive_spans=True)
    data = [
        {'spans': [[0,4]], 'name': 'LOC', 'value': '5', 'category': '[fact]', 'color': '#ff0000'},
        {'spans': [[4,6]], 'name': 'LOC', 'value': '6', 'color': '#00ff00'},
        {'spans': [[4,10]], 'name': 'PER', 'value': '5', 'category': '[fact]', 'color': '#0000ff'},
        {'spans': [[10,15]], 'name': 'ORG', 'value': '5', 'color': '#0000ff'},
    ]
    print(hl.highlight("Mina olen ilus mees. Mul on relv ka.", data, 'Mina olen ilus mees. <span style="background-color: #ff0000" class="[ES]">Mul on relv ka</span>.'))
