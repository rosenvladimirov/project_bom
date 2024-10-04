/** @odoo-module **/

import {useService} from "@web/core/utils/hooks";
import {onWillStart, useState} from "@odoo/owl";

odoo.define('pv_config.ProductTemplateAttributeLineExtend', [
    '@web/core/utils/patch',
    '@sale_product_configurator/js/product_template_attribute_line/product_template_attribute_line'
], function (require) {
    const {patch} = require('@web/core/utils/patch');
    const ProductTemplateAttributeLine = require('@sale_product_configurator/js/product_template_attribute_line/product_template_attribute_line');

    if (ProductTemplateAttributeLine && ProductTemplateAttributeLine.ProductTemplateAttributeLine && ProductTemplateAttributeLine.ProductTemplateAttributeLine.prototype) {
        const parentMethod = ProductTemplateAttributeLine.ProductTemplateAttributeLine.prototype.getPTAVTemplate;
        patch(ProductTemplateAttributeLine.ProductTemplateAttributeLine.prototype, {
            setup() {
                this.rpc = useService("rpc");
                this.state = useState({
                    headers: [],
                });
                onWillStart(() => {
                    this.rpc('/pv_config/get_headers', {
                        product_template_id: this.props.productTmplId
                    }).then((headers) => {
                        this.state.headers = headers;
                    });
                    // for (const ptav of this.props.attribute_values) {
                    //     this.state.ptavValidState[ptav.id] = true;
                    //     this.rpc('/pv_config/get_ptav_is_valid', {
                    //         ptav_id: ptav.id
                    //     }).then((isValid) => {
                    //         this.state.ptavValidState[ptav.id] = isValid;
                    //     });
                    // }
                });
            },
            getPTAVTemplate() {
                const template = parentMethod.apply(this, arguments);
                if (template === 'saleProductConfigurator.ptav-radio') {
                    return 'pv_config.ptav-radio-extend';
                }
                return template;
            }
        });
    }
});
